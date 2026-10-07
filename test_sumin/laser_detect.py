# laser_detect.py

import cv2
import numpy as np

def detect_red_laser(frame, h_lo, h_hi, h_lo2, h_hi2,
                     s_min, v_min, blur_k, area_min):

    k = blur_k if blur_k % 2 == 1 else blur_k + 1
    k = max(k, 1)

    blurred = cv2.GaussianBlur(frame, (k, k), 0)

    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

    m1 = cv2.inRange(
        hsv,
        np.array([h_lo, s_min, v_min]),
        np.array([h_hi, 255, 255])
    )

    m2 = cv2.inRange(
        hsv,
        np.array([h_lo2, s_min, v_min]),
        np.array([h_hi2, 255, 255])
    )

    mask = cv2.bitwise_or(m1, m2)

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    if contours:
        c = max(contours, key=cv2.contourArea)

        if cv2.contourArea(c) > area_min:
            M = cv2.moments(c)

            if M["m00"] != 0:
                cx = int(M["m10"]/M["m00"])
                cy = int(M["m01"]/M["m00"])

                return cx, cy, mask

    return None, None, mask