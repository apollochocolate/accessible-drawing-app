import cv2
import numpy as np
from collections import deque

# =========================
# Basic Settings
# =========================
CAMERA_INDEX = 0

R_MIN = 160
RED_DIFF = 60

MIN_AREA = 10
MAX_AREA = 5000
MAX_W_H = 200

# =========================
# Keyboard Mapping (warp 기준 좌표)
# =========================
key_map = {
    "Q": (50, 50, 120, 120),
    "W": (130, 50, 200, 120),
    "E": (210, 50, 280, 120),
    "A": (70, 130, 140, 200),
    "S": (150, 130, 220, 200),
    "D": (230, 130, 300, 200),
}

# =========================
# Homography
# =========================
points = []
H = None

def mouse_callback(event, x, y, flags, param):
    global points
    if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4:
        points.append([x, y])
        print(f"[Calibration] Point {len(points)}: {x}, {y}")

def find_key(x, y):
    for key, (x1, y1, x2, y2) in key_map.items():
        if x1 <= x <= x2 and y1 <= y <= y2:
            return key
    return None

# =========================
# Camera Open
# =========================
cap = cv2.VideoCapture(CAMERA_INDEX)

if not cap.isOpened():
    print("Cannot open camera.")
    exit()

cv2.namedWindow("Laser Keyboard")
cv2.setMouseCallback("Laser Keyboard", mouse_callback)

# =========================
# Smoothing
# =========================
x_history = deque(maxlen=3)
y_history = deque(maxlen=3)

print("Click 4 corners of keyboard (TL → TR → BR → BL)")
print("Press q or ESC to quit")

try:
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        display = frame.copy()

        # =========================
        # Laser Detection (RGB 기반)
        # =========================
        b, g, r = cv2.split(frame)

        r_i = r.astype(np.int16)
        g_i = g.astype(np.int16)
        b_i = b.astype(np.int16)

        laser_pixel = (
            (r_i > R_MIN) &
            (r_i > g_i + RED_DIFF) &
            (r_i > b_i + RED_DIFF)
        )

        mask = laser_pixel.astype(np.uint8) * 255

        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.medianBlur(mask, 3)

        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        best_candidate = None
        best_score = -1

        for contour in contours:
            area = cv2.contourArea(contour)

            if not (MIN_AREA < area < MAX_AREA):
                continue

            x, y, w, h = cv2.boundingRect(contour)

            if w > MAX_W_H or h > MAX_W_H:
                continue

            ratio = w / h if h != 0 else 0
            if ratio < 0.4 or ratio > 2.5:
                continue

            M = cv2.moments(contour)
            if M["m00"] == 0:
                continue

            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

            score = int(r[cy, cx]) + area

            if score > best_score:
                best_score = score
                best_candidate = (cx, cy)

        # =========================
        # Homography 생성
        # =========================
        if len(points) == 4 and H is None:
            pts_src = np.array(points, dtype=np.float32)
            pts_dst = np.array([[0,0],[400,0],[400,300],[0,300]], dtype=np.float32)
            H = cv2.getPerspectiveTransform(pts_src, pts_dst)
            print("[INFO] Homography ready")

        # =========================
        # Laser detected
        # =========================
        if best_candidate is not None:
            raw_x, raw_y = best_candidate

            x_history.append(raw_x)
            y_history.append(raw_y)

            laser_x = int(sum(x_history) / len(x_history))
            laser_y = int(sum(y_history) / len(y_history))

            cv2.circle(display, (laser_x, laser_y), 10, (0,255,0), 2)

            # =========================
            # 좌표 변환 + 키 매핑
            # =========================
            if H is not None:
                pt = np.array([[[laser_x, laser_y]]], dtype=np.float32)
                transformed = cv2.perspectiveTransform(pt, H)

                tx = int(transformed[0][0][0])
                ty = int(transformed[0][0][1])

                key = find_key(tx, ty)

                if key:
                    print(f">>> KEY PRESSED: {key}")

                    cv2.putText(
                        display,
                        f"KEY: {key}",
                        (laser_x, laser_y - 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (0,0,255),
                        2
                    )

        else:
            x_history.clear()
            y_history.clear()

        # =========================
        # UI 표시
        # =========================
        for p in points:
            cv2.circle(display, tuple(p), 5, (255,0,0), -1)

        if len(points) < 4:
            cv2.putText(display, "Click 4 corners", (10,30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)

        cv2.imshow("Laser Keyboard", display)
        # cv2.imshow("Mask", mask)

        key = cv2.waitKey(1) & 0xFF
        if key == 27 or key == ord('q'):
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
