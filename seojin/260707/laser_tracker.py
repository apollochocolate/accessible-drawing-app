"""
laser_tracker.py
카메라 화면에서 실제 레이저 점 후보를 찾는 파일.
레이저가 없으면 None을 반환해서 아무거나 인식하지 않게 합니다.
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
)


def detect_laser(frame, prefer_point=None):
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

    hue_red_or_pink = (h_i <= 18) | (h_i >= 155)

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
        & (hue_red_or_pink | (s_i >= 25))
    )

    laser_pixel = color_candidate | core_candidate
    mask = laser_pixel.astype(np.uint8) * 255
    mask = cv2.medianBlur(mask, 3)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    score_img = (
        v_i.astype(np.float32) * 1.4
        + r_i.astype(np.float32) * 1.0
        + s_i.astype(np.float32) * 0.4
        + np.maximum(red_over_green, 0).astype(np.float32) * 3.5
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
        if ratio < 0.2 or ratio > 5.0:
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

        x1 = max(cx - 4, 0)
        x2 = min(cx + 5, frame.shape[1])
        y1 = max(cy - 4, 0)
        y2 = min(cy + 5, frame.shape[0])

        local_r = float(np.mean(r[y1:y2, x1:x2]))
        local_g = float(np.mean(g[y1:y2, x1:x2]))
        local_s = float(np.mean(s_ch[y1:y2, x1:x2]))
        local_v = float(np.mean(v[y1:y2, x1:x2]))
        local_red_green = local_r - local_g

        score = float(max_score) + core_pixels * 15 + local_v * 0.8 + max(local_red_green, 0) * 2.5

        if prefer_point and prefer_point[0] is not None and prefer_point[1] is not None:
            px, py = prefer_point
            dist = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
            if dist < 120:
                score += 100 - dist * 0.4
            else:
                score -= min(dist * 0.25, 140)

        candidates.append({
            "x": int(cx),
            "y": int(cy),
            "area": float(area),
            "score": float(score),
            "red_strength": float(local_red_green),
            "v": float(local_v),
            "s": float(local_s),
            "w": int(w),
            "h": int(h_box),
            "core": int(core_pixels),
        })

    if not candidates:
        return None

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates[0]
