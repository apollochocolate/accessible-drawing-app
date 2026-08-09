"""
laser_tracker.py

카메라 화면에서 실제 레이저 점 후보를 찾는 파일.

v3 레이저 민감도 개선
- 1차: 기존처럼 밝고 빨간 레이저 중심부를 엄격하게 찾음
- 2차: 1차가 실패하면 종이 영역 안에서 "주변보다 가장 붉게 튀는 작은 점"을 동적 기준으로 다시 찾음
- 이전 위치 근처 후보는 더 신뢰해서 화면이 왔다갔다하는 현상을 줄임
"""

import cv2
import numpy as np

from config_combined import (
    R_MIN,
    RED_DIFF,
    HSV_S_MIN,
    HSV_V_MIN,
    MIN_AREA,
    MAX_AREA,
    MAX_W_H,
    MIN_FILL_RATIO,
    MIN_LASER_SCORE,
    LASER_CORE_R_MIN,
    LASER_CORE_V_MIN,
    LASER_CORE_RED_DIFF,
    MIN_CORE_PIXELS,
    LASER_NEAR_PREVIOUS_BONUS_RADIUS,
    LASER_FAR_PREVIOUS_PENALTY,
    LASER_MIN_LOCAL_RED_DIFF,
    LASER_MIN_LOCAL_V,
    LASER_ENABLE_DYNAMIC_FALLBACK,
    LASER_DYNAMIC_PERCENTILE,
    LASER_DYNAMIC_MIN_SCORE,
    LASER_DYNAMIC_MIN_LOCAL_RED_DIFF,
    LASER_DYNAMIC_MIN_LOCAL_V,
    LASER_DYNAMIC_MAX_AREA,
    LASER_DYNAMIC_MAX_W_H,
    LASER_DYNAMIC_MIN_SUPPORT_PIXELS,
    LASER_DYNAMIC_CONFIRM_MARGIN,
    USE_LASER_BACKGROUND_FILTER,
    LASER_BG_MIN_R_DELTA,
    LASER_BG_MIN_V_DELTA,
    LASER_BG_MIN_REDNESS_DELTA,
    LASER_BG_STRONG_REDNESS_DELTA,
    LASER_BG_MASK_DILATE,
)


def _prefer_previous_bonus(cx, cy, score, prefer_point):
    """이전 레이저 위치 근처 후보를 우선해서 갑자기 튀는 현상을 줄입니다."""
    if not (prefer_point and prefer_point[0] is not None and prefer_point[1] is not None):
        return score

    px, py = prefer_point
    dist = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5

    if dist < LASER_NEAR_PREVIOUS_BONUS_RADIUS:
        score += (LASER_NEAR_PREVIOUS_BONUS_RADIUS - dist) * 3.0 + 160
    else:
        score -= min(dist * LASER_FAR_PREVIOUS_PENALTY, 900)

    return score


def _local_stats(r, g, s_ch, v, cx, cy, radius=4):
    x1 = max(cx - radius, 0)
    x2 = min(cx + radius + 1, r.shape[1])
    y1 = max(cy - radius, 0)
    y2 = min(cy + radius + 1, r.shape[0])

    local_r = float(np.mean(r[y1:y2, x1:x2]))
    local_g = float(np.mean(g[y1:y2, x1:x2]))
    local_s = float(np.mean(s_ch[y1:y2, x1:x2]))
    local_v = float(np.mean(v[y1:y2, x1:x2]))

    return local_r, local_g, local_s, local_v, local_r - local_g


def _build_color_arrays(frame):
    b, g, r = cv2.split(frame)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, s_ch, v = cv2.split(hsv)

    r_i = r.astype(np.int16)
    g_i = g.astype(np.int16)
    b_i = b.astype(np.int16)
    h_i = h.astype(np.int16)
    s_i = s_ch.astype(np.int16)
    v_i = v.astype(np.int16)

    red_over_green = r_i - g_i
    red_over_blue = r_i - b_i
    hue_red_or_pink = (h_i <= 20) | (h_i >= 150)

    return b, g, r, h, s_ch, v, r_i, g_i, b_i, h_i, s_i, v_i, red_over_green, red_over_blue, hue_red_or_pink



def build_laser_change_mask(frame, background_frame):
    """
    실행 초기에 저장한 배경과 현재 프레임을 비교해서
    '새로 생긴 빨간 점'만 통과시키는 마스크를 만듭니다.

    목적:
    - 종이에 원래 있던 빨간 잡점/모니터 반사/프린트 색은 제거
    - 실제 레이저를 켰을 때 새로 생기는 붉은 밝기 변화만 남김
    """
    if background_frame is None or not USE_LASER_BACKGROUND_FILTER:
        return None

    if background_frame.shape[:2] != frame.shape[:2]:
        background_frame = cv2.resize(background_frame, (frame.shape[1], frame.shape[0]))

    b, g, r = cv2.split(frame)
    bg_b, bg_g, bg_r = cv2.split(background_frame)

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    _, s_ch, v = cv2.split(hsv)
    bg_hsv = cv2.cvtColor(background_frame, cv2.COLOR_BGR2HSV)
    _, _, bg_v = cv2.split(bg_hsv)

    r_i = r.astype(np.int16)
    g_i = g.astype(np.int16)
    b_i = b.astype(np.int16)
    v_i = v.astype(np.int16)
    s_i = s_ch.astype(np.int16)

    bg_r_i = bg_r.astype(np.int16)
    bg_g_i = bg_g.astype(np.int16)
    bg_b_i = bg_b.astype(np.int16)
    bg_v_i = bg_v.astype(np.int16)

    # 단순 밝기 증가만 보면 자동노출 변화도 잡히므로,
    # 빨간 성분이 주변 색보다 얼마나 더 늘었는지를 같이 봅니다.
    current_redness = r_i - np.maximum(g_i, b_i)
    background_redness = bg_r_i - np.maximum(bg_g_i, bg_b_i)

    r_delta = r_i - bg_r_i
    v_delta = v_i - bg_v_i
    redness_delta = current_redness - background_redness

    change = (
        (
            (redness_delta >= LASER_BG_MIN_REDNESS_DELTA)
            & (r_delta >= LASER_BG_MIN_R_DELTA)
        )
        |
        (
            (redness_delta >= LASER_BG_STRONG_REDNESS_DELTA)
            & (v_delta >= LASER_BG_MIN_V_DELTA)
        )
    )

    # 너무 어두운 픽셀이나 채도가 거의 없는 픽셀은 제외합니다.
    change = change & (r_i >= 80) & (v_i >= 45) & (s_i >= 20)

    mask = change.astype(np.uint8) * 255
    mask = cv2.medianBlur(mask, 3)

    if LASER_BG_MASK_DILATE > 0:
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=int(LASER_BG_MASK_DILATE))

    return mask


def _combine_allowed_masks(mask_a, mask_b):
    if mask_a is None:
        return mask_b
    if mask_b is None:
        return mask_a
    return cv2.bitwise_and(mask_a, mask_b)


def _strict_candidates(frame, prefer_point=None, allowed_mask=None):
    (
        b, g, r, h, s_ch, v,
        r_i, g_i, b_i, h_i, s_i, v_i,
        red_over_green, red_over_blue, hue_red_or_pink
    ) = _build_color_arrays(frame)

    color_candidate = (
        hue_red_or_pink
        & (s_i >= HSV_S_MIN)
        & (v_i >= HSV_V_MIN)
        & (r_i >= R_MIN)
        & (red_over_green >= RED_DIFF)
        & (red_over_blue >= -20)
    )

    core_candidate = (
        (r_i >= LASER_CORE_R_MIN)
        & (v_i >= LASER_CORE_V_MIN)
        & (red_over_green >= LASER_CORE_RED_DIFF)
        & (hue_red_or_pink | (s_i >= 28))
    )

    if allowed_mask is not None:
        allowed = allowed_mask > 0
        color_candidate &= allowed
        core_candidate &= allowed

    laser_pixel = color_candidate | core_candidate
    mask = laser_pixel.astype(np.uint8) * 255
    mask = cv2.medianBlur(mask, 3)

    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    score_img = (
        v_i.astype(np.float32) * 1.35
        + r_i.astype(np.float32) * 1.0
        + s_i.astype(np.float32) * 0.45
        + np.maximum(red_over_green, 0).astype(np.float32) * 4.2
    )

    candidates = []

    for contour in contours:
        area = cv2.contourArea(contour)
        if not (MIN_AREA <= area <= MAX_AREA):
            continue

        x, y, w, h_box = cv2.boundingRect(contour)
        if w <= 0 or h_box <= 0:
            continue
        if w > MAX_W_H or h_box > MAX_W_H:
            continue

        ratio = w / h_box
        if ratio < 0.18 or ratio > 5.5:
            continue

        fill_ratio = area / max(w * h_box, 1)
        if fill_ratio < MIN_FILL_RATIO:
            continue

        core_roi = core_candidate[y:y + h_box, x:x + w]
        core_pixels = int(np.count_nonzero(core_roi))
        if core_pixels < MIN_CORE_PIXELS:
            continue

        component_mask = np.zeros(mask.shape, dtype=np.uint8)
        cv2.drawContours(component_mask, [contour], -1, 255, -1)
        masked_score = np.where(component_mask > 0, score_img, -1)
        _, max_score, _, max_loc = cv2.minMaxLoc(masked_score.astype(np.float32))
        cx, cy = max_loc

        if max_score < MIN_LASER_SCORE:
            continue

        local_r, local_g, local_s, local_v, local_red_green = _local_stats(r, g, s_ch, v, cx, cy)

        if local_red_green < LASER_MIN_LOCAL_RED_DIFF:
            continue
        if local_v < LASER_MIN_LOCAL_V:
            continue

        score = (
            float(max_score)
            + core_pixels * 18
            + local_v * 0.9
            + max(local_red_green, 0) * 3.4
            - area * 0.02
        )
        score = _prefer_previous_bonus(cx, cy, score, prefer_point)

        candidates.append({
            "x": int(cx),
            "y": int(cy),
            "area": float(area),
            "score": float(score),
            "raw_score": float(max_score),
            "red_strength": float(local_red_green),
            "v": float(local_v),
            "s": float(local_s),
            "w": int(w),
            "h": int(h_box),
            "core": int(core_pixels),
            "mode": "strict",
        })

    return candidates


def _dynamic_fallback_candidates(frame, prefer_point=None, allowed_mask=None):
    """
    strict 기준으로 못 잡았을 때 쓰는 보조 검출.
    흰 종이 위에서는 레이저가 카메라에서 아주 약하게 보일 수 있어서,
    절대 밝기보다 '주변보다 붉게 튀는 정도'를 더 봅니다.
    """
    (
        b, g, r, h, s_ch, v,
        r_i, g_i, b_i, h_i, s_i, v_i,
        red_over_green, red_over_blue, hue_red_or_pink
    ) = _build_color_arrays(frame)

    if allowed_mask is not None:
        allowed = allowed_mask > 0
    else:
        allowed = np.ones(frame.shape[:2], dtype=bool)

    # 검은 마커/글자 쪽은 빨간 점으로 착각하기 쉬워서 너무 어두운 곳은 제외
    allowed = allowed & (v_i >= 35)

    # 빨간 정도 점수. R-G와 R-B를 같이 보되, 너무 어두운 픽셀은 약하게 봄.
    red_score = (
        np.maximum(red_over_green, 0).astype(np.float32) * 4.8
        + np.maximum(red_over_blue, 0).astype(np.float32) * 1.4
        + s_i.astype(np.float32) * 0.55
        + v_i.astype(np.float32) * 0.22
    )

    red_score = np.where(allowed, red_score, -9999.0)

    valid_scores = red_score[allowed]
    if valid_scores.size < 20:
        return []

    dyn_thr = float(np.percentile(valid_scores, LASER_DYNAMIC_PERCENTILE))
    dyn_thr = max(dyn_thr, float(LASER_DYNAMIC_MIN_SCORE))

    # hue 조건을 너무 강하게 걸면 카메라에서 분홍/주황으로 튄 레이저를 놓칠 수 있어 완화함.
    pixel = (
        allowed
        & (red_score >= dyn_thr)
        & (red_over_green >= LASER_DYNAMIC_MIN_LOCAL_RED_DIFF)
        & ((hue_red_or_pink) | (s_i >= 25))
    )

    mask = pixel.astype(np.uint8) * 255
    mask = cv2.medianBlur(mask, 3)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []

    for contour in contours:
        area = cv2.contourArea(contour)
        if not (1 <= area <= LASER_DYNAMIC_MAX_AREA):
            continue

        x, y, w, h_box = cv2.boundingRect(contour)
        if w <= 0 or h_box <= 0:
            continue
        if w > LASER_DYNAMIC_MAX_W_H or h_box > LASER_DYNAMIC_MAX_W_H:
            continue

        # 가느다란 선/글자 가장자리는 제외
        ratio = w / h_box
        if ratio < 0.16 or ratio > 6.5:
            continue

        roi_pixel = pixel[y:y + h_box, x:x + w]
        support_pixels = int(np.count_nonzero(roi_pixel))
        if support_pixels < LASER_DYNAMIC_MIN_SUPPORT_PIXELS:
            continue

        component_mask = np.zeros(mask.shape, dtype=np.uint8)
        cv2.drawContours(component_mask, [contour], -1, 255, -1)
        masked_score = np.where(component_mask > 0, red_score, -9999.0)
        _, max_score, _, max_loc = cv2.minMaxLoc(masked_score.astype(np.float32))
        cx, cy = max_loc

        local_r, local_g, local_s, local_v, local_red_green = _local_stats(r, g, s_ch, v, cx, cy, radius=5)

        if local_red_green < LASER_DYNAMIC_MIN_LOCAL_RED_DIFF:
            continue
        if local_v < LASER_DYNAMIC_MIN_LOCAL_V:
            continue

        score = float(max_score) + support_pixels * 8 + max(local_red_green, 0) * 5 + local_v * 0.3
        score = _prefer_previous_bonus(cx, cy, score, prefer_point)

        candidates.append({
            "x": int(cx),
            "y": int(cy),
            "area": float(area),
            "score": float(score),
            "raw_score": float(max_score),
            "red_strength": float(local_red_green),
            "v": float(local_v),
            "s": float(local_s),
            "w": int(w),
            "h": int(h_box),
            "core": int(support_pixels),
            "mode": "fallback",
            "thr": float(dyn_thr),
        })

    # 후보가 너무 많으면 노이즈가 많은 상황일 수 있음.
    # 단, 이전 위치가 있으면 그 근처 후보는 살릴 수 있으므로 정렬 후 상위 후보의 차이를 봅니다.
    candidates.sort(key=lambda item: item["score"], reverse=True)

    if len(candidates) >= 2:
        # 1등과 2등이 거의 같으면 랜덤 잡점일 가능성이 높음.
        # 이전 위치가 있는 경우에는 prefer bonus가 들어가서 1등이 확실해지는 편.
        if candidates[0]["score"] - candidates[1]["score"] < LASER_DYNAMIC_CONFIRM_MARGIN:
            if not (prefer_point and prefer_point[0] is not None and prefer_point[1] is not None):
                return []

    return candidates


def detect_laser(frame, prefer_point=None, allowed_mask=None, background_frame=None):
    """
    레이저 점 후보 1개를 반환합니다.

    background_frame이 있으면 실행 초기에 저장한 배경과 비교해서
    새로 생긴 빨간 점만 후보로 봅니다.
    그래서 종이에 원래 있던 빨간 잡점/반사광/모니터 색을 훨씬 덜 잡습니다.
    """
    change_mask = build_laser_change_mask(frame, background_frame)
    effective_allowed_mask = _combine_allowed_masks(allowed_mask, change_mask)

    candidates = _strict_candidates(
        frame,
        prefer_point=prefer_point,
        allowed_mask=effective_allowed_mask,
    )

    if not candidates and LASER_ENABLE_DYNAMIC_FALLBACK:
        candidates = _dynamic_fallback_candidates(
            frame,
            prefer_point=prefer_point,
            allowed_mask=effective_allowed_mask,
        )

    if not candidates:
        return None

    candidates.sort(key=lambda item: item["score"], reverse=True)
    best = candidates[0]
    if change_mask is not None:
        best["bg_filter"] = True
    return best
