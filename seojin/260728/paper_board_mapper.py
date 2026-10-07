"""
paper_board_mapper.py

A3 세로 종이 키보드의 네 모서리 검은 마커를 인식해서
카메라 좌표를 종이 디자인 좌표로 보정하는 모듈입니다.

Space anchor 버전
- 네 모서리 마커로 종이 전체 좌표계를 먼저 만듭니다.
- 그다음 종이 안에서 가장 긴 하단 키인 Space 박스를 찾아 키보드 위치를 추가 보정합니다.
- 나머지 키는 OCR로 읽지 않고, Space 기준으로 보정된 좌표계에서 기존 KEY_MAP 상대 위치를 사용합니다.
"""

import cv2
import numpy as np

from config_combined import (
    WIN_W,
    WIN_H,
    MOUSE_ZONE_Y,
    PAPER_DESIGN_W,
    PAPER_DESIGN_H,
    PAPER_MARKER_CENTERS,
    PAPER_KEYBOARD_BOX,
    VIRTUAL_KEYBOARD_BOX,
    PAPER_MOUSE_X1,
    PAPER_MOUSE_X2,
    PAPER_MOUSE_LINE_Y,
    PAPER_MOUSE_BOTTOM_Y,
    MARKER_DARK_THRESHOLD,
    MARKER_MIN_AREA_RATIO,
    MARKER_MAX_AREA_RATIO,
    MARKER_MIN_SQUARE_RATIO,
    MARKER_MAX_SQUARE_RATIO,
    MARKER_MIN_FILL_RATIO,
)

try:
    from config_combined import (
        USE_SPACE_ANCHOR,
        SPACE_ANCHOR_SEARCH_BOX,
        SPACE_ANCHOR_DARK_THRESHOLD,
        SPACE_ANCHOR_MIN_ASPECT,
        SPACE_ANCHOR_MAX_ASPECT,
        SPACE_ANCHOR_MIN_WIDTH_RATIO,
        SPACE_ANCHOR_MAX_WIDTH_RATIO,
        SPACE_ANCHOR_MIN_HEIGHT_RATIO,
        SPACE_ANCHOR_MAX_HEIGHT_RATIO,
        SPACE_ANCHOR_MAX_CENTER_SHIFT,
        SPACE_ANCHOR_ALPHA,
        SPACE_ANCHOR_KEEP_FRAMES,
        SPACE_ANCHOR_WARP_SCALE,
        SPACE_ANCHOR_DRAW_DEBUG,
    )
except Exception:
    USE_SPACE_ANCHOR = False
    SPACE_ANCHOR_SEARCH_BOX = None
    SPACE_ANCHOR_DARK_THRESHOLD = 150
    SPACE_ANCHOR_MIN_ASPECT = 2.1
    SPACE_ANCHOR_MAX_ASPECT = 8.0
    SPACE_ANCHOR_MIN_WIDTH_RATIO = 0.45
    SPACE_ANCHOR_MAX_WIDTH_RATIO = 1.75
    SPACE_ANCHOR_MIN_HEIGHT_RATIO = 0.35
    SPACE_ANCHOR_MAX_HEIGHT_RATIO = 2.0
    SPACE_ANCHOR_MAX_CENTER_SHIFT = 420.0
    SPACE_ANCHOR_ALPHA = 0.35
    SPACE_ANCHOR_KEEP_FRAMES = 25
    SPACE_ANCHOR_WARP_SCALE = 0.25
    SPACE_ANCHOR_DRAW_DEBUG = True

try:
    from keyboard_layout import KEY_MAP
except Exception:
    KEY_MAP = {}


def _order_points_tl_tr_bl_br(points):
    """네 점을 왼쪽 위, 오른쪽 위, 왼쪽 아래, 오른쪽 아래 순서로 정렬."""
    pts = np.asarray(points, dtype=np.float32)
    if len(pts) != 4:
        return None

    by_y = pts[np.argsort(pts[:, 1])]
    top = by_y[:2]
    bottom = by_y[2:]

    top = top[np.argsort(top[:, 0])]
    bottom = bottom[np.argsort(bottom[:, 0])]

    return np.array([top[0], top[1], bottom[0], bottom[1]], dtype=np.float32)


def _rect_center(rect):
    x1, y1, x2, y2 = rect
    return (float(x1 + x2) / 2.0, float(y1 + y2) / 2.0)


def _shift_rect(rect, dx, dy):
    x1, y1, x2, y2 = rect
    return (float(x1 + dx), float(y1 + dy), float(x2 + dx), float(y2 + dy))


def _blend_rect(old_rect, new_rect, alpha):
    if old_rect is None:
        return tuple(float(v) for v in new_rect)
    return tuple(float(o * (1.0 - alpha) + n * alpha) for o, n in zip(old_rect, new_rect))


class PaperBoardMapper:
    def __init__(self):
        self.camera_to_paper_h = None
        self.paper_to_camera_h = None
        self.last_markers = []
        self.last_status = "Marker board not ready"
        self.last_debug = ""
        self.ref_marker_centers = np.asarray(PAPER_MARKER_CENTERS, dtype=np.float32)

        # Space 기준점 보정 상태
        self.dynamic_keyboard_box = tuple(float(v) for v in PAPER_KEYBOARD_BOX)
        self.last_space_anchor = None
        self.last_space_status = "Space anchor not ready"
        self.space_missing_frames = 999

    def update(self, frame):
        """현재 프레임에서 마커 4개를 찾아 homography를 갱신합니다."""
        markers = self._detect_markers(frame)
        self.last_markers = markers

        if len(markers) < 4:
            self.last_status = f"Markers {len(markers)}/4"
            self.space_missing_frames += 1
            return False

        # 후보가 4개보다 많으면 면적이 큰 후보를 우선 사용합니다.
        markers = sorted(markers, key=lambda item: item["area"], reverse=True)[:4]
        centers = [m["center"] for m in markers]
        ordered = _order_points_tl_tr_bl_br(centers)

        if ordered is None:
            self.last_status = "Marker ordering failed"
            self.space_missing_frames += 1
            return False

        h, _ = cv2.findHomography(ordered, self.ref_marker_centers, method=0)
        if h is None:
            self.last_status = "Homography failed"
            self.space_missing_frames += 1
            return False

        self.camera_to_paper_h = h
        self.paper_to_camera_h = np.linalg.inv(h)
        self.last_status = "Marker board OK"

        if USE_SPACE_ANCHOR:
            self._update_space_anchor(frame)
        else:
            self.dynamic_keyboard_box = tuple(float(v) for v in PAPER_KEYBOARD_BOX)
            self.last_space_status = "Space anchor OFF"

        return True

    def ready(self):
        return self.camera_to_paper_h is not None

    def get_active_keyboard_box(self):
        if USE_SPACE_ANCHOR and self.dynamic_keyboard_box is not None:
            # Space를 잠깐 놓쳐도 이전 보정값을 몇 프레임 유지합니다.
            if self.space_missing_frames <= SPACE_ANCHOR_KEEP_FRAMES:
                return self.dynamic_keyboard_box
        return tuple(float(v) for v in PAPER_KEYBOARD_BOX)

    def _detect_markers(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (3, 3), 0)

        frame_h, frame_w = frame.shape[:2]
        frame_area = frame_h * frame_w
        min_area = frame_area * MARKER_MIN_AREA_RATIO
        max_area = frame_area * MARKER_MAX_AREA_RATIO

        thresholds = []
        for t in [MARKER_DARK_THRESHOLD, 100, 120, 140, 160]:
            if t not in thresholds:
                thresholds.append(t)

        best_markers = []
        best_thr = thresholds[0]

        for thr in thresholds:
            mask = (blur < thr).astype(np.uint8)
            kernel = np.ones((3, 3), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)

            markers = []
            for i in range(1, num_labels):
                x, y, w, h, area = stats[i]
                area = float(area)

                if not (min_area <= area <= max_area):
                    continue
                if w <= 0 or h <= 0:
                    continue
                if x <= 1 or y <= 1 or x + w >= frame_w - 1 or y + h >= frame_h - 1:
                    continue

                square_ratio = w / float(h)
                if not (MARKER_MIN_SQUARE_RATIO <= square_ratio <= MARKER_MAX_SQUARE_RATIO):
                    continue

                fill_ratio = area / max(w * h, 1)
                if fill_ratio < MARKER_MIN_FILL_RATIO:
                    continue
                if w < 10 or h < 10:
                    continue

                cx, cy = centroids[i]
                markers.append({
                    "bbox": (int(x), int(y), int(w), int(h)),
                    "center": (float(cx), float(cy)),
                    "area": float(area),
                    "fill": float(fill_ratio),
                    "thr": int(thr),
                })

            if len(markers) >= 4:
                best_markers = markers
                best_thr = thr
                break

            if len(markers) > len(best_markers):
                best_markers = markers
                best_thr = thr

        self.last_debug = f"thr={best_thr}, candidates={len(best_markers)}"
        return best_markers

    def _virtual_rect_to_paper_with_box(self, rect, keyboard_box):
        x1, y1, x2, y2 = rect
        kx1, ky1, kx2, ky2 = keyboard_box
        vx1, vy1, vx2, vy2 = VIRTUAL_KEYBOARD_BOX

        def one(vx, vy):
            px = kx1 + (float(vx) - vx1) * (kx2 - kx1) / max(vx2 - vx1, 1e-6)
            py = ky1 + (float(vy) - vy1) * (ky2 - ky1) / max(vy2 - vy1, 1e-6)
            return px, py

        p1 = one(x1, y1)
        p2 = one(x2, y2)
        return (float(p1[0]), float(p1[1]), float(p2[0]), float(p2[1]))

    def _space_virtual_rect(self):
        return KEY_MAP.get("Space", (212, 240, 326, 282))

    def _expected_space_paper_rect(self, keyboard_box=None):
        return self._virtual_rect_to_paper_with_box(
            self._space_virtual_rect(),
            keyboard_box or tuple(float(v) for v in PAPER_KEYBOARD_BOX),
        )

    def _make_scaled_homography(self, scale):
        s = np.array([
            [scale, 0.0, 0.0],
            [0.0, scale, 0.0],
            [0.0, 0.0, 1.0],
        ], dtype=np.float32)
        return s @ self.camera_to_paper_h

    def _update_space_anchor(self, frame):
        """종이 안에서 Space 키 박스를 찾아 키보드 좌표를 보정합니다."""
        self.last_space_anchor = None

        if self.camera_to_paper_h is None:
            self.last_space_status = "Space anchor: no paper H"
            self.space_missing_frames += 1
            return False

        scale = float(SPACE_ANCHOR_WARP_SCALE)
        out_w = max(1, int(PAPER_DESIGN_W * scale))
        out_h = max(1, int(PAPER_DESIGN_H * scale))

        try:
            h_scaled = self._make_scaled_homography(scale)
            warped = cv2.warpPerspective(frame, h_scaled, (out_w, out_h))
        except Exception as exc:
            self.last_space_status = f"Space anchor warp error: {exc}"
            self.space_missing_frames += 1
            return False

        if SPACE_ANCHOR_SEARCH_BOX:
            sx1, sy1, sx2, sy2 = SPACE_ANCHOR_SEARCH_BOX
        else:
            pred = self._expected_space_paper_rect(tuple(float(v) for v in PAPER_KEYBOARD_BOX))
            px1, py1, px2, py2 = pred
            sx1, sy1, sx2, sy2 = px1 - 650, py1 - 300, px2 + 650, py2 + 300

        x1 = int(max(0, min(out_w - 1, sx1 * scale)))
        y1 = int(max(0, min(out_h - 1, sy1 * scale)))
        x2 = int(max(0, min(out_w, sx2 * scale)))
        y2 = int(max(0, min(out_h, sy2 * scale)))

        if x2 <= x1 + 10 or y2 <= y1 + 10:
            self.last_space_status = "Space anchor: bad search box"
            self.space_missing_frames += 1
            return False

        roi = warped[y1:y2, x1:x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        # 검은 키 테두리/글자를 흰색으로 만든 마스크.
        _, mask = cv2.threshold(gray, int(SPACE_ANCHOR_DARK_THRESHOLD), 255, cv2.THRESH_BINARY_INV)
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        expected_space = self._expected_space_paper_rect(tuple(float(v) for v in PAPER_KEYBOARD_BOX))
        esx1, esy1, esx2, esy2 = expected_space
        expected_w = max((esx2 - esx1) * scale, 1.0)
        expected_h = max((esy2 - esy1) * scale, 1.0)
        expected_cx = ((esx1 + esx2) / 2.0) * scale
        expected_cy = ((esy1 + esy2) / 2.0) * scale

        candidates = []
        for contour in contours:
            bx, by, bw, bh = cv2.boundingRect(contour)
            if bw <= 0 or bh <= 0:
                continue

            aspect = bw / float(bh)
            if not (SPACE_ANCHOR_MIN_ASPECT <= aspect <= SPACE_ANCHOR_MAX_ASPECT):
                continue

            if not (expected_w * SPACE_ANCHOR_MIN_WIDTH_RATIO <= bw <= expected_w * SPACE_ANCHOR_MAX_WIDTH_RATIO):
                continue
            if not (expected_h * SPACE_ANCHOR_MIN_HEIGHT_RATIO <= bh <= expected_h * SPACE_ANCHOR_MAX_HEIGHT_RATIO):
                continue

            full_x1 = x1 + bx
            full_y1 = y1 + by
            full_x2 = full_x1 + bw
            full_y2 = full_y1 + bh
            cx = full_x1 + bw / 2.0
            cy = full_y1 + bh / 2.0

            # Space는 하단 중앙 부근의 가장 긴 키입니다.
            dist = ((cx - expected_cx) ** 2 + ((cy - expected_cy) * 1.35) ** 2) ** 0.5
            width_score = bw / expected_w
            aspect_score = 1.0 / (1.0 + abs(aspect - (expected_w / expected_h)))
            score = width_score * 120.0 + aspect_score * 80.0 - dist * 0.18

            candidates.append({
                "rect_scaled": (full_x1, full_y1, full_x2, full_y2),
                "center_scaled": (cx, cy),
                "w": float(bw),
                "h": float(bh),
                "aspect": float(aspect),
                "score": float(score),
                "dist": float(dist),
            })

        if not candidates:
            self.space_missing_frames += 1
            if self.space_missing_frames <= SPACE_ANCHOR_KEEP_FRAMES and self.dynamic_keyboard_box is not None:
                self.last_space_status = f"Space anchor keep {self.space_missing_frames}/{SPACE_ANCHOR_KEEP_FRAMES}"
            else:
                self.dynamic_keyboard_box = tuple(float(v) for v in PAPER_KEYBOARD_BOX)
                self.last_space_status = "Space anchor not found"
            return False

        candidates.sort(key=lambda item: item["score"], reverse=True)
        best = candidates[0]
        rx1, ry1, rx2, ry2 = best["rect_scaled"]

        detected_rect = (
            float(rx1) / scale,
            float(ry1) / scale,
            float(rx2) / scale,
            float(ry2) / scale,
        )
        detected_center = _rect_center(detected_rect)
        expected_center = _rect_center(expected_space)
        dx = detected_center[0] - expected_center[0]
        dy = detected_center[1] - expected_center[1]
        shift = (dx * dx + dy * dy) ** 0.5

        if shift > float(SPACE_ANCHOR_MAX_CENTER_SHIFT):
            self.space_missing_frames += 1
            self.last_space_status = f"Space anchor rejected shift={shift:.0f}"
            return False

        target_box = _shift_rect(tuple(float(v) for v in PAPER_KEYBOARD_BOX), dx, dy)
        self.dynamic_keyboard_box = _blend_rect(self.dynamic_keyboard_box, target_box, float(SPACE_ANCHOR_ALPHA))
        self.last_space_anchor = detected_rect
        self.space_missing_frames = 0
        self.last_space_status = (
            f"Space anchor OK dx={dx:.0f} dy={dy:.0f} "
            f"score={best['score']:.0f}"
        )
        return True

    def paper_polygon_to_camera(self, paper_points):
        """종이 디자인 좌표의 다각형을 카메라 좌표 다각형으로 변환."""
        if self.paper_to_camera_h is None:
            return None

        camera_points = []
        for px, py in paper_points:
            cp = self.paper_to_camera(px, py)
            if cp is None:
                return None
            camera_points.append(cp)

        return np.asarray(camera_points, dtype=np.int32)

    def get_paper_mask(self, frame_shape, margin=12):
        """레이저 검출을 종이 내부로 제한하기 위한 0/255 마스크 생성."""
        if self.paper_to_camera_h is None:
            return None

        frame_h, frame_w = frame_shape[:2]
        pts = [
            (float(margin), float(margin)),
            (float(PAPER_DESIGN_W - margin), float(margin)),
            (float(PAPER_DESIGN_W - margin), float(PAPER_DESIGN_H - margin)),
            (float(margin), float(PAPER_DESIGN_H - margin)),
        ]
        poly = self.paper_polygon_to_camera(pts)
        if poly is None:
            return None

        mask = np.zeros((frame_h, frame_w), dtype=np.uint8)
        cv2.fillPoly(mask, [poly], 255)

        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)
        return mask

    def camera_to_paper(self, x, y):
        if self.camera_to_paper_h is None:
            return None
        point = np.array([[[float(x), float(y)]]], dtype=np.float32)
        mapped = cv2.perspectiveTransform(point, self.camera_to_paper_h)[0][0]
        return float(mapped[0]), float(mapped[1])

    def paper_to_camera(self, x, y):
        if self.paper_to_camera_h is None:
            return None
        point = np.array([[[float(x), float(y)]]], dtype=np.float32)
        mapped = cv2.perspectiveTransform(point, self.paper_to_camera_h)[0][0]
        return float(mapped[0]), float(mapped[1])

    def camera_to_virtual(self, x, y):
        """카메라 레이저 좌표 -> 기존 640x480 가상 좌표로 변환."""
        paper_point = self.camera_to_paper(x, y)
        if paper_point is None:
            return {"ok": False, "zone": "outside"}

        px, py = paper_point

        kx1, ky1, kx2, ky2 = self.get_active_keyboard_box()
        vx1, vy1, vx2, vy2 = VIRTUAL_KEYBOARD_BOX

        if kx1 <= px <= kx2 and ky1 <= py <= ky2:
            vx = vx1 + (px - kx1) * (vx2 - vx1) / max(kx2 - kx1, 1e-6)
            vy = vy1 + (py - ky1) * (vy2 - vy1) / max(ky2 - ky1, 1e-6)
            return {
                "ok": True,
                "zone": "keyboard",
                "x": float(vx),
                "y": float(vy),
                "paper_x": float(px),
                "paper_y": float(py),
            }

        if PAPER_MOUSE_X1 <= px <= PAPER_MOUSE_X2 and py >= PAPER_MOUSE_LINE_Y:
            rel_x = (px - PAPER_MOUSE_X1) / max(PAPER_MOUSE_X2 - PAPER_MOUSE_X1, 1e-6)
            rel_y = (py - PAPER_MOUSE_LINE_Y) / max(PAPER_MOUSE_BOTTOM_Y - PAPER_MOUSE_LINE_Y, 1e-6)
            rel_x = max(0.0, min(1.0, rel_x))
            rel_y = max(0.0, min(1.0, rel_y))
            vx = rel_x * WIN_W
            vy = MOUSE_ZONE_Y + rel_y * (WIN_H - MOUSE_ZONE_Y)
            return {
                "ok": True,
                "zone": "mouse",
                "x": float(vx),
                "y": float(vy),
                "paper_x": float(px),
                "paper_y": float(py),
            }

        return {
            "ok": True,
            "zone": "outside",
            "x": None,
            "y": None,
            "paper_x": float(px),
            "paper_y": float(py),
        }

    def virtual_keyboard_rect_to_camera_poly(self, rect):
        if self.paper_to_camera_h is None:
            return None

        x1, y1, x2, y2 = rect
        kx1, ky1, kx2, ky2 = self.get_active_keyboard_box()
        vx1, vy1, vx2, vy2 = VIRTUAL_KEYBOARD_BOX

        def virtual_to_paper(vx, vy):
            px = kx1 + (vx - vx1) * (kx2 - kx1) / max(vx2 - vx1, 1e-6)
            py = ky1 + (vy - vy1) * (ky2 - ky1) / max(vy2 - vy1, 1e-6)
            return px, py

        paper_points = [
            virtual_to_paper(x1, y1),
            virtual_to_paper(x2, y1),
            virtual_to_paper(x2, y2),
            virtual_to_paper(x1, y2),
        ]

        camera_points = []
        for px, py in paper_points:
            cp = self.paper_to_camera(px, py)
            if cp is None:
                return None
            camera_points.append(cp)

        return np.asarray(camera_points, dtype=np.int32)

    def paper_rect_to_camera_poly(self, rect):
        x1, y1, x2, y2 = rect
        pts = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        return self.paper_polygon_to_camera(pts)

    def draw_debug(self, frame, hovered_key=None, key_map=None):
        color = (0, 255, 0) if self.ready() else (0, 0, 255)
        cv2.putText(
            frame,
            self.last_status,
            (10, 455),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
        )
        cv2.putText(
            frame,
            self.last_debug,
            (10, 430),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
        )
        cv2.putText(
            frame,
            self.last_space_status,
            (10, 407),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 180, 0) if "OK" in self.last_space_status or "keep" in self.last_space_status else (0, 0, 255),
            1,
        )

        for marker in self.last_markers:
            x, y, w, h = marker["bbox"]
            cx, cy = marker["center"]
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 255), 2)
            cv2.circle(frame, (int(cx), int(cy)), 4, (255, 0, 255), -1)

        if SPACE_ANCHOR_DRAW_DEBUG and self.last_space_anchor is not None:
            poly = self.paper_rect_to_camera_poly(self.last_space_anchor)
            if poly is not None:
                cv2.polylines(frame, [poly], True, (255, 180, 0), 2)
                cx = int(np.mean(poly[:, 0]))
                cy = int(np.mean(poly[:, 1]))
                cv2.putText(
                    frame,
                    "Space anchor",
                    (cx + 8, cy - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 180, 0),
                    2,
                )

        if hovered_key and key_map and hovered_key in key_map:
            poly = self.virtual_keyboard_rect_to_camera_poly(key_map[hovered_key])
            if poly is not None:
                cv2.polylines(frame, [poly], True, (0, 255, 0), 3)
                cx = int(np.mean(poly[:, 0]))
                cy = int(np.mean(poly[:, 1]))
                cv2.putText(
                    frame,
                    hovered_key,
                    (cx + 8, cy - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )
