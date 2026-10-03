"""
paper_edge_mapper.py

용지 테두리 자동 인식 버전 mapper 입니다.

paper_board_mapper.PaperBoardMapper 와 완전히 같은 외부 인터페이스
(update / camera_to_virtual / get_paper_mask / draw_debug 등)를 제공하되,
네 모서리 검은 마커 대신 "종이 사각형 외곽선"을 직접 찾아
카메라 좌표를 종이 디자인 좌표로 보정합니다.

- 종이에 마커를 인쇄할 필요가 없습니다.
- 좌표 변환 / Space anchor / 종이 마스크 로직은 PaperBoardMapper 것을 그대로 재사용합니다.
- 검출 결과(네 꼭짓점)만 다르게 얻어서 findHomography 에 넣습니다.

config_combined.PAPER_MAPPER_MODE 값으로 marker/edge 방식을 전환합니다.
이 모듈은 기존 방식을 전혀 건드리지 않습니다.
"""

import cv2
import numpy as np

from config_combined import (
    PAPER_DESIGN_W,
    PAPER_DESIGN_H,
    PAPER_KEYBOARD_BOX,
    USE_SPACE_ANCHOR,
)

from paper_board_mapper import (
    PaperBoardMapper,
    _order_points_tl_tr_bl_br,
)

# 용지 테두리 검출 설정을 config 에서 가져옵니다.
# config 에 값이 없어도 동작하도록 기본값을 함께 준비합니다.
try:
    from config_combined import (
        PAPER_EDGE_USE_CANNY,
        PAPER_EDGE_CANNY_LOW,
        PAPER_EDGE_CANNY_HIGH,
        PAPER_EDGE_MIN_AREA_RATIO,
        PAPER_EDGE_MAX_AREA_RATIO,
        PAPER_EDGE_APPROX_EPS_RATIO,
        PAPER_EDGE_ASPECT_TARGET,
        PAPER_EDGE_ASPECT_TOLERANCE,
        PAPER_EDGE_MARGIN,
        PAPER_EDGE_SMOOTH_ALPHA,
        PAPER_EDGE_DRAW_DEBUG,
        PAPER_EDGE_HOLD_FRAMES,
        PAPER_EDGE_MAX_CENTER_SHIFT,
    )
except Exception:
    PAPER_EDGE_USE_CANNY = True
    PAPER_EDGE_CANNY_LOW = 50
    PAPER_EDGE_CANNY_HIGH = 150
    PAPER_EDGE_MIN_AREA_RATIO = 0.08
    PAPER_EDGE_MAX_AREA_RATIO = 0.98
    PAPER_EDGE_APPROX_EPS_RATIO = 0.02
    PAPER_EDGE_ASPECT_TARGET = float(PAPER_DESIGN_H) / float(PAPER_DESIGN_W)
    PAPER_EDGE_ASPECT_TOLERANCE = 0.35
    PAPER_EDGE_MARGIN = 0.0
    PAPER_EDGE_SMOOTH_ALPHA = 0.5
    PAPER_EDGE_DRAW_DEBUG = True
    PAPER_EDGE_HOLD_FRAMES = 10
    PAPER_EDGE_MAX_CENTER_SHIFT = 150.0


class PaperEdgeMapper(PaperBoardMapper):
    """종이 외곽선을 찾아 homography 를 만드는 mapper."""

    def __init__(self):
        super().__init__()

        # 마커 방식은 4개 마커 중심(PAPER_MARKER_CENTERS)으로 정렬했지만,
        # 테두리 방식은 종이 물리적 네 꼭짓점을 디자인 네 모서리로 매핑합니다.
        m = float(PAPER_EDGE_MARGIN)
        self.ref_corners = np.array(
            [
                [m, m],                                     # 왼쪽 위
                [PAPER_DESIGN_W - m, m],                    # 오른쪽 위
                [m, PAPER_DESIGN_H - m],                    # 왼쪽 아래
                [PAPER_DESIGN_W - m, PAPER_DESIGN_H - m],   # 오른쪽 아래
            ],
            dtype=np.float32,
        )

        self.last_quad = None          # 가장 최근에 찾은 종이 사각형(정렬 전 4점)
        self.last_ordered = None       # EMA 스무딩된 정렬 후 4점(TL,TR,BL,BR)
        self.quad_missing_frames = 0   # last_quad 를 언제까지 유지할지 세는 카운터

    # ------------------------------------------------------------------
    # 메인 업데이트
    # ------------------------------------------------------------------
    def update(self, frame, detect_frame=None):
        """현재 프레임에서 종이 사각형을 찾아 homography 를 갱신합니다.

        frame: 640x480 기준 프레임. homography / Space anchor 좌표계는 항상 이 프레임 기준입니다.
        detect_frame: 종이 사각형 검출에 쓸 고해상도 프레임(선택). 주어지면 이 프레임에서 사각형을
        찾고 좌표만 frame 크기 기준으로 환산합니다 — 검출 정밀도만 올리고, 레이저 매핑/Space anchor
        등 나머지 좌표계는 그대로 640x480을 유지합니다.
        """
        detect_src = detect_frame if detect_frame is not None else frame
        quad = self._detect_paper_quad(detect_src)

        if quad is not None and detect_frame is not None:
            sx = frame.shape[1] / float(detect_frame.shape[1])
            sy = frame.shape[0] / float(detect_frame.shape[0])
            quad = quad * np.array([sx, sy], dtype=np.float32)

        # 부모 draw_debug 가 self.last_markers 를 순회하므로 비워둡니다.
        self.last_markers = []

        if quad is None:
            self._register_quad_miss("Paper edge not found")
            return False

        ordered = _order_points_tl_tr_bl_br(quad)
        if ordered is None:
            self._register_quad_miss("Paper quad ordering failed")
            return False

        if self.last_ordered is not None:
            prev_center = self.last_ordered.mean(axis=0)
            new_center = ordered.mean(axis=0)
            shift = float(np.linalg.norm(new_center - prev_center))
            if shift > float(PAPER_EDGE_MAX_CENTER_SHIFT):
                self._register_quad_miss(f"Paper edge rejected shift={shift:.0f}")
                return False

        # 여기까지 왔으면 이번 프레임 검출은 신뢰할 만합니다 — 표시용 사각형을 갱신합니다.
        self.quad_missing_frames = 0
        self.last_quad = quad

        # 프레임마다 꼭짓점이 미세하게 떨리므로 EMA 로 안정화합니다.
        alpha = float(PAPER_EDGE_SMOOTH_ALPHA)
        if self.last_ordered is not None and 0.0 < alpha < 1.0:
            ordered = self.last_ordered * (1.0 - alpha) + ordered * alpha
        self.last_ordered = ordered

        h, _ = cv2.findHomography(ordered, self.ref_corners, method=0)
        if h is None:
            self._register_quad_miss("Homography failed")
            return False

        self.camera_to_paper_h = h
        self.paper_to_camera_h = np.linalg.inv(h)
        self.last_status = "Paper edge OK"

        if USE_SPACE_ANCHOR:
            # Space anchor 로직은 부모 것을 그대로 사용하며, homography가 640x480 좌표계
            # 기준이므로 항상 저해상도 frame 으로 호출합니다(고해상도를 넣으면 warp가 어긋남).
            self._update_space_anchor(frame)
        else:
            self.dynamic_keyboard_box = tuple(float(v) for v in PAPER_KEYBOARD_BOX)
            self.last_space_status = "Space anchor OFF"

        return True

    def _register_quad_miss(self, status):
        """검출 실패/이상치 거부를 공통 처리합니다.

        PAPER_EDGE_HOLD_FRAMES 프레임 이내에는 last_quad(오버레이용)를 이전 값 그대로 유지해서,
        손이 모서리를 잠깐 스치는 정도의 순간적인 실패로는 노란 사각형이 깜빡이지 않게 합니다.
        """
        self.quad_missing_frames += 1
        self.space_missing_frames += 1
        self.last_status = status
        if self.quad_missing_frames > PAPER_EDGE_HOLD_FRAMES:
            self.last_quad = None

    # ------------------------------------------------------------------
    # 종이 사각형 검출
    # ------------------------------------------------------------------
    def _detect_paper_quad(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        frame_h, frame_w = frame.shape[:2]
        frame_area = float(frame_h * frame_w)

        kernel = np.ones((5, 5), np.uint8)
        if PAPER_EDGE_USE_CANNY:
            # 종이 테두리를 에지로 잡습니다. 흰 종이/밝은 배경 대비가 약해도
            # 경계 자체는 대체로 살아 있어서 Canny 가 잘 맞습니다.
            bin_img = cv2.Canny(blur, int(PAPER_EDGE_CANNY_LOW), int(PAPER_EDGE_CANNY_HIGH))
            bin_img = cv2.dilate(bin_img, kernel, iterations=1)
            bin_img = cv2.morphologyEx(bin_img, cv2.MORPH_CLOSE, kernel, iterations=2)
        else:
            # 어두운 책상 위 밝은 종이라면 Otsu 이진화가 더 안정적입니다.
            _, bin_img = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            bin_img = cv2.morphologyEx(bin_img, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(bin_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            self.last_debug = "edge: no contours"
            return None

        min_area = frame_area * float(PAPER_EDGE_MIN_AREA_RATIO)
        max_area = frame_area * float(PAPER_EDGE_MAX_AREA_RATIO)

        # A3 세로 종이의 목표 종횡비(긴 변/짧은 변).
        target_aspect = float(PAPER_EDGE_ASPECT_TARGET)
        if target_aspect > 0 and target_aspect < 1.0:
            target_aspect = 1.0 / target_aspect

        best_quad = None
        best_area = 0.0

        # 면적 큰 후보부터 몇 개만 검사합니다.
        for c in sorted(contours, key=cv2.contourArea, reverse=True)[:8]:
            area = float(cv2.contourArea(c))
            if area < min_area or area > max_area:
                continue

            # 종이는 볼록하므로 convex hull 로 먼저 정리합니다.
            # Canny+팽창으로 생긴 두꺼운 테두리 링/작은 요철이나
            # 손·레이저가 테두리를 살짝 가려도 사각형을 안정적으로 뽑습니다.
            hull = cv2.convexHull(c)
            peri = cv2.arcLength(hull, True)
            if peri <= 0:
                continue

            approx = None
            base_eps = float(PAPER_EDGE_APPROX_EPS_RATIO)
            for eps in (base_eps, base_eps * 1.5, base_eps * 2.0, base_eps * 3.0):
                cand = cv2.approxPolyDP(hull, eps * peri, True)
                if len(cand) == 4:
                    approx = cand
                    break
            if approx is None or not cv2.isContourConvex(approx):
                continue

            pts = approx.reshape(4, 2).astype(np.float32)

            # 종횡비로 명백히 다른 사각형(모니터, 책상 모서리 등)을 걸러냅니다.
            if target_aspect > 0:
                (rw, rh) = cv2.minAreaRect(pts)[1]
                if rw <= 1 or rh <= 1:
                    continue
                aspect = max(rw, rh) / min(rw, rh)
                if abs(aspect - target_aspect) > float(PAPER_EDGE_ASPECT_TOLERANCE) * target_aspect:
                    continue

            if area > best_area:
                best_area = area
                best_quad = pts

        self.last_debug = (
            f"edge: contours={len(contours)} "
            f"quad={'Y' if best_quad is not None else 'N'}"
        )
        return best_quad

    # ------------------------------------------------------------------
    # 디버그 표시: 부모 표시 + 찾은 종이 외곽선
    # ------------------------------------------------------------------
    def draw_debug(self, frame, hovered_key=None, key_map=None):
        super().draw_debug(frame, hovered_key, key_map)

        if PAPER_EDGE_DRAW_DEBUG and self.last_quad is not None and self.last_ordered is not None:
            # last_ordered 는 EMA 로 스무딩된 좌표라서, raw last_quad 를 다시 정렬해서 그리는 것보다
            # 오버레이가 덜 흔들립니다(표시 여부 자체는 last_quad 의 hold 상태를 따릅니다).
            # 정렬 순서는 TL,TR,BL,BR 이므로 폴리라인용으로 TL,TR,BR,BL 재배치.
            poly = np.asarray(self.last_ordered, dtype=np.int32)[[0, 1, 3, 2]]
            cv2.polylines(frame, [poly], True, (0, 255, 255), 2)
            for px, py in poly:
                cv2.circle(frame, (int(px), int(py)), 5, (0, 255, 255), -1)
