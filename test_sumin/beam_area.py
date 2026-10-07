import cv2
import numpy as np

WIN_W, WIN_H = 640, 480

# ===========================
# Beam(ROI) Area
# ===========================
ROI_X = 120
ROI_Y = 100
ROI_W = 400
ROI_H = 260


def detect_red_laser(frame, h_lo, h_hi, h_lo2, h_hi2, s_min, v_min, blur_k, area_min):
    k = blur_k if blur_k % 2 == 1 else blur_k + 1
    k = max(k, 1)

    blurred = cv2.GaussianBlur(frame, (k, k), 0)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

    m1 = cv2.inRange(hsv, np.array([h_lo, s_min, v_min]), np.array([h_hi, 255, 255]))
    m2 = cv2.inRange(hsv, np.array([h_lo2, s_min, v_min]), np.array([h_hi2, 255, 255]))

    mask = cv2.bitwise_or(m1, m2)

    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.dilate(mask, kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        c = max(contours, key=cv2.contourArea)

        if cv2.contourArea(c) > area_min:
            M = cv2.moments(c)

            if M["m00"] != 0:
                x = int(M["m10"] / M["m00"])
                y = int(M["m01"] / M["m00"])
                return x, y, mask

    return None, None, mask


def is_inside_beam(x, y):
    return ROI_X <= x <= ROI_X + ROI_W and ROI_Y <= y <= ROI_Y + ROI_H


def draw_beam(frame, inside):
    overlay = frame.copy()

    color = (0, 255, 0) if inside else (0, 0, 255)

    cv2.rectangle(
        overlay,
        (ROI_X, ROI_Y),
        (ROI_X + ROI_W, ROI_Y + ROI_H),
        color,
        -1
    )

    cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)

    cv2.rectangle(
        frame,
        (ROI_X, ROI_Y),
        (ROI_X + ROI_W, ROI_Y + ROI_H),
        color,
        3
    )

    cv2.putText(
        frame,
        "BEAM AREA",
        (ROI_X + 10, ROI_Y - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        color,
        2
    )


cv2.namedWindow("HSV")

cv2.createTrackbar("H_low1", "HSV", 0, 10, lambda x: None)
cv2.createTrackbar("H_high1", "HSV", 10, 30, lambda x: None)
cv2.createTrackbar("H_low2", "HSV", 160, 180, lambda x: None)
cv2.createTrackbar("H_high2", "HSV", 180, 180, lambda x: None)
cv2.createTrackbar("S_min", "HSV", 80, 255, lambda x: None)
cv2.createTrackbar("V_min", "HSV", 100, 255, lambda x: None)
cv2.createTrackbar("Blur", "HSV", 5, 21, lambda x: None)
cv2.createTrackbar("Area", "HSV", 5, 200, lambda x: None)

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIN_W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WIN_H)

show_mask = False

while True:

    ret, frame = cap.read()

    if not ret:
        break

    frame = cv2.flip(frame, 1)

    h_lo = cv2.getTrackbarPos("H_low1", "HSV")
    h_hi = cv2.getTrackbarPos("H_high1", "HSV")
    h_lo2 = cv2.getTrackbarPos("H_low2", "HSV")
    h_hi2 = cv2.getTrackbarPos("H_high2", "HSV")
    s_min = cv2.getTrackbarPos("S_min", "HSV")
    v_min = cv2.getTrackbarPos("V_min", "HSV")
    blur = max(cv2.getTrackbarPos("Blur", "HSV"), 1)
    area = cv2.getTrackbarPos("Area", "HSV")

    cx, cy, mask = detect_red_laser(
        frame,
        h_lo, h_hi,
        h_lo2, h_hi2,
        s_min, v_min,
        blur,
        area
    )

    inside = False

    if cx is not None:

        inside = is_inside_beam(cx, cy)

        cv2.circle(frame, (cx, cy), 8, (0, 255, 255), -1)
        cv2.circle(frame, (cx, cy), 12, (255, 255, 255), 2)

    draw_beam(frame, inside)

    status = "INSIDE BEAM AREA" if inside else "OUTSIDE"

    cv2.putText(
        frame,
        status,
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0,255,0) if inside else (0,0,255),
        2
    )

    cv2.imshow("Beam Area", frame)

    if show_mask:
        cv2.imshow("Mask", mask)

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break

    elif key == ord("m"):
        show_mask = not show_mask
        if not show_mask:
            cv2.destroyWindow("Mask")

cap.release()
cv2.destroyAllWindows()
