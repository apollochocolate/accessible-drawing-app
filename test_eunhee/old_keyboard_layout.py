import cv2
import numpy as np
from collections import deque

# =========================
# Basic Settings
# =========================
CAMERA_INDEX = 1

R_MIN = 160
RED_DIFF = 60

MIN_AREA = 10
MAX_AREA = 5000
MAX_W_H = 200

# =========================
# Keyboard Layout Definition (화면 좌표)
# 각 키: "key_name": (x1, y1, x2, y2)
# =========================

# 키보드 시작 위치
START_X = 10
START_Y = 10
KEY_WIDTH = 60
KEY_HEIGHT = 50
H_GAP = 5  # 수평 간격
V_GAP = 5  # 수직 간격


def calc_key_rect(col, row, width_multiplier=1, height_multiplier=1):
    """
    그리드 기반으로 키 좌표 계산
    col, row: 그리드 위치
    width_multiplier, height_multiplier: 키 크기 배수
    """
    x1 = START_X + col * (KEY_WIDTH + H_GAP)
    y1 = START_Y + row * (KEY_HEIGHT + V_GAP)
    x2 = x1 + KEY_WIDTH * width_multiplier + H_GAP * (width_multiplier - 1)
    y2 = y1 + KEY_HEIGHT * height_multiplier + V_GAP * (height_multiplier - 1)
    return (x1, y1, x2, y2)


# 첫 번째 줄 (ESC, F키들)
key_map = {
    "ESC": calc_key_rect(0, 0),
    "F1": calc_key_rect(2, 0),
    "F2": calc_key_rect(3, 0),
    "F3": calc_key_rect(4, 0),
    "F4": calc_key_rect(5, 0),
    "F5": calc_key_rect(7, 0),
    "F6": calc_key_rect(8, 0),
    "F7": calc_key_rect(9, 0),
    "F8": calc_key_rect(10, 0),
    "F9": calc_key_rect(11, 0),
    "F10": calc_key_rect(12, 0),
    "F11": calc_key_rect(13, 0),
    "F12": calc_key_rect(14, 0),
    "PrtSc": calc_key_rect(15, 0),
    "ScrLk": calc_key_rect(16, 0),
    "Pause": calc_key_rect(17, 0),
}

# 두 번째 줄 (숫자열)
second_row = {
    "`": calc_key_rect(0, 1),
    "1": calc_key_rect(1, 1),
    "2": calc_key_rect(2, 1),
    "3": calc_key_rect(3, 1),
    "4": calc_key_rect(4, 1),
    "5": calc_key_rect(5, 1),
    "6": calc_key_rect(6, 1),
    "7": calc_key_rect(7, 1),
    "8": calc_key_rect(8, 1),
    "9": calc_key_rect(9, 1),
    "0": calc_key_rect(10, 1),
    "-": calc_key_rect(11, 1),
    "=": calc_key_rect(12, 1),
    "BackSpace": calc_key_rect(13, 1, 1.5),
    "Insert": calc_key_rect(15, 1),
    "Home": calc_key_rect(16, 1),
    "PageUp": calc_key_rect(17, 1),
}

# 세 번째 줄 (QWERTY열)
third_row = {
    "Tab": calc_key_rect(0, 2, 1.3),
    "Q": calc_key_rect(1.5, 2),
    "W": calc_key_rect(2.5, 2),
    "E": calc_key_rect(3.5, 2),
    "R": calc_key_rect(4.5, 2),
    "T": calc_key_rect(5.5, 2),
    "Y": calc_key_rect(6.5, 2),
    "U": calc_key_rect(7.5, 2),
    "I": calc_key_rect(8.5, 2),
    "O": calc_key_rect(9.5, 2),
    "P": calc_key_rect(10.5, 2),
    "[": calc_key_rect(11.5, 2),
    "]": calc_key_rect(12.5, 2),
    "\\": calc_key_rect(13.5, 2, 1.2),
    "Delete": calc_key_rect(15, 2),
    "End": calc_key_rect(16, 2),
    "PageDn": calc_key_rect(17, 2),
}

# 네 번째 줄 (ASDF열)
fourth_row = {
    "Caps": calc_key_rect(0, 3, 1.8),
    "A": calc_key_rect(2, 3),
    "S": calc_key_rect(3, 3),
    "D": calc_key_rect(4, 3),
    "F": calc_key_rect(5, 3),
    "G": calc_key_rect(6, 3),
    "H": calc_key_rect(7, 3),
    "J": calc_key_rect(8, 3),
    "K": calc_key_rect(9, 3),
    "L": calc_key_rect(10, 3),
    ";": calc_key_rect(11, 3),
    "'": calc_key_rect(12, 3),
    "Enter": calc_key_rect(13, 3, 1.8),
}

# 다섯 번째 줄 (ZXCV열)
fifth_row = {
    "Shift": calc_key_rect(0, 4, 1.3),
    "Z": calc_key_rect(1.5, 4),
    "X": calc_key_rect(2.5, 4),
    "C": calc_key_rect(3.5, 4),
    "V": calc_key_rect(4.5, 4),
    "B": calc_key_rect(5.5, 4),
    "N": calc_key_rect(6.5, 4),
    "M": calc_key_rect(7.5, 4),
    ",": calc_key_rect(8.5, 4),
    ".": calc_key_rect(9.5, 4),
    "/": calc_key_rect(10.5, 4),
    "ShiftR": calc_key_rect(11.5, 4, 2.2),
    "Up": calc_key_rect(16, 4),
}

# 여섯 번째 줄 (스페이스바, Ctrl, Alt)
sixth_row = {
    "Ctrl": calc_key_rect(0, 5, 1.3),
    "Fn": calc_key_rect(1.5, 5),
    "Alt": calc_key_rect(2.7, 5),
    "Space": calc_key_rect(4, 5, 6.5),
    "AltR": calc_key_rect(10.5, 5),
    "CtrlR": calc_key_rect(11.8, 5, 1.2),
    "Left": calc_key_rect(15, 5),
    "Down": calc_key_rect(16, 5),
    "Right": calc_key_rect(17, 5),
}

# 모든 키 맵 통합
key_map.update(second_row)
key_map.update(third_row)
key_map.update(fourth_row)
key_map.update(fifth_row)
key_map.update(sixth_row)


def find_key(x, y):
    """
    레이저 좌표 (x, y)로 키 이름 찾기
    """
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

cv2.namedWindow("Laser Keyboard Layout")

# =========================
# Smoothing & Key Tracking
# =========================
x_history = deque(maxlen=3)
y_history = deque(maxlen=3)
previous_key = None  # 이전 감지된 키 저장

print("Press q or ESC to quit")
print(f"Total keys: {len(key_map)}")

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

        laser_pixel = (r_i > R_MIN) & (r_i > g_i + RED_DIFF) & (r_i > b_i + RED_DIFF)

        mask = laser_pixel.astype(np.uint8) * 255

        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.medianBlur(mask, 3)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

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
        # Laser detected
        # =========================
        if best_candidate is not None:
            raw_x, raw_y = best_candidate

            x_history.append(raw_x)
            y_history.append(raw_y)

            laser_x = int(sum(x_history) / len(x_history))
            laser_y = int(sum(y_history) / len(y_history))

            cv2.circle(display, (laser_x, laser_y), 10, (0, 255, 0), 2)

            # =========================
            # 키 매핑
            # =========================
            key = find_key(laser_x, laser_y)

            if key:
                # 키가 변경되었을 때만 프린트
                if key != previous_key:
                    print(f">>> KEY PRESSED: {key}")
                    previous_key = key

                cv2.putText(
                    display,
                    f"KEY: {key}",
                    (laser_x, laser_y - 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2,
                )
            else:
                previous_key = None

        else:
            x_history.clear()
            y_history.clear()
            previous_key = None

        # =========================
        # 키보드 UI 표시 (모든 키 그리기)
        # =========================
        for key, (x1, y1, x2, y2) in key_map.items():
            cv2.rectangle(
                display, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 0), 1
            )

            # 키 레이블 크기 조정
            font_size = 0.35
            if len(key) > 3:
                font_size = 0.3

            text_size = cv2.getTextSize(key, cv2.FONT_HERSHEY_SIMPLEX, font_size, 1)[0]
            text_x = int((x1 + x2) / 2 - text_size[0] / 2)
            text_y = int((y1 + y2) / 2 + text_size[1] / 2)

            cv2.putText(
                display,
                key,
                (text_x, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_size,
                (255, 0, 0),
                1,
            )

        cv2.imshow("Laser Keyboard Layout", display)
        # cv2.imshow("Mask", mask)

        key = cv2.waitKey(1) & 0xFF
        if key == 27 or key == ord("q"):
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
