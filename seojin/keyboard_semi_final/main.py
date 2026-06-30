# main.py

import cv2
import numpy as np
import pyautogui

from keyboard_layout import KEY_MAP
from laser_detect import detect_red_laser
from renderer import draw_keyboard_overlay
from shortcut_manager import (
    process_key,
    reset_key_state,
    get_active_modifier,
    get_allowed_keys
)


# =========================
# 기본 설정
# =========================
WIN_W = 640
WIN_H = 480

# 키보드/마우스 판을 비추는 카메라 번호
# 안 나오면 0, 1, 2로 바꿔보기
CAMERA_INDEX = 0

# Windows 기준
CAMERA_BACKEND = cv2.CAP_DSHOW

# Mac이면 위 줄 대신 아래 줄 사용
# CAMERA_BACKEND = cv2.CAP_AVFOUNDATION


# =========================
# 영역 구분
# =========================
# renderer.py에서 그린 구분선 위치와 맞춤
# y < 250  : 키보드 영역
# y >= 250 : 마우스 이동 영역
MOUSE_ZONE_Y = 250


# =========================
# 레이저 인식 고정값
# =========================
H_LOW1 = 0
H_HIGH1 = 10

H_LOW2 = 160
H_HIGH2 = 180

S_MIN = 80
V_MIN = 100

BLUR_K = 5
AREA_MIN = 5


# =========================
# 마우스 이동 보정값
# =========================
SMOOTHING_ALPHA = 0.25   # 작을수록 부드럽고 느림, 클수록 빠름
MOUSE_DEAD_ZONE = 4      # 이 픽셀 이하는 흔들림으로 보고 무시

smoothed_mouse_x = None
smoothed_mouse_y = None

screen_w, screen_h = pyautogui.size()

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0


# =========================
# 키 위치 찾기
# =========================
def get_key_at(x, y):
    for name, (x1, y1, x2, y2) in KEY_MAP.items():
        if x1 <= x <= x2 and y1 <= y <= y2:
            return name
    return None


# =========================
# 마우스 영역 좌표를 실제 모니터 좌표로 변환
# =========================
def mouse_zone_to_screen(x, y):
    # x는 전체 가로 기준
    rel_x = x / WIN_W

    # y는 구분선 아래 영역만 기준
    mouse_zone_h = WIN_H - MOUSE_ZONE_Y
    rel_y = (y - MOUSE_ZONE_Y) / mouse_zone_h

    rel_x = max(0, min(1, rel_x))
    rel_y = max(0, min(1, rel_y))

    screen_x = int(rel_x * screen_w)
    screen_y = int(rel_y * screen_h)

    screen_x = max(0, min(screen_w - 1, screen_x))
    screen_y = max(0, min(screen_h - 1, screen_y))

    return screen_x, screen_y


# =========================
# 카메라 열기
# =========================
cap = cv2.VideoCapture(CAMERA_INDEX, CAMERA_BACKEND)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIN_W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WIN_H)

for _ in range(10):
    cap.read()


print("실행 중...")
print("q : 종료")
print("구분선 위: 키보드 영역")
print("구분선 아래: 마우스 이동 영역")


# =========================
# 메인 루프
# =========================
while True:
    ret, frame = cap.read()

    if not ret or frame is None or frame.size == 0:
        frame = np.zeros((WIN_H, WIN_W, 3), dtype=np.uint8)

    frame = cv2.resize(frame, (WIN_W, WIN_H))

    # 카메라 좌우가 반대로 느껴지면 아래 주석 해제
    # frame = cv2.flip(frame, 1)

    cx, cy, mask = detect_red_laser(
        frame,
        H_LOW1,
        H_HIGH1,
        H_LOW2,
        H_HIGH2,
        S_MIN,
        V_MIN,
        BLUR_K,
        AREA_MIN
    )

    detected_key = None
    laser_detected = cx is not None and cy is not None

    if laser_detected:
        is_mouse_zone = cy >= MOUSE_ZONE_Y

        # 레이저 위치 표시
        cv2.circle(frame, (cx, cy), 8, (0, 0, 255), -1)
        cv2.circle(frame, (cx, cy), 12, (255, 255, 255), 2)

        # =========================
        # 구분선 아래: 마우스 이동 영역
        # =========================
        if is_mouse_zone:
            reset_key_state()

            screen_x, screen_y = mouse_zone_to_screen(cx, cy)

            if smoothed_mouse_x is None or smoothed_mouse_y is None:
                smoothed_mouse_x = screen_x
                smoothed_mouse_y = screen_y
            else:
                smoothed_mouse_x = int(
                    smoothed_mouse_x * (1 - SMOOTHING_ALPHA)
                    + screen_x * SMOOTHING_ALPHA
                )
                smoothed_mouse_y = int(
                    smoothed_mouse_y * (1 - SMOOTHING_ALPHA)
                    + screen_y * SMOOTHING_ALPHA
                )

            current_mouse_x, current_mouse_y = pyautogui.position()

            mouse_diff = (
                (smoothed_mouse_x - current_mouse_x) ** 2
                + (smoothed_mouse_y - current_mouse_y) ** 2
            ) ** 0.5

            if mouse_diff > MOUSE_DEAD_ZONE:
                try:
                    pyautogui.moveTo(smoothed_mouse_x, smoothed_mouse_y)
                except pyautogui.FailSafeException:
                    print("PyAutoGUI fail-safe 작동. 종료합니다.")
                    break

            cv2.putText(
                frame,
                "MOUSE AREA",
                (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2
            )

        # =========================
        # 구분선 위: 키보드 영역
        # =========================
        else:
            smoothed_mouse_x = None
            smoothed_mouse_y = None

            detected_key = get_key_at(cx, cy)

            active_modifier = get_active_modifier()

            if active_modifier is not None:
                allowed_keys = get_allowed_keys(active_modifier)

                modifier_keys = {
                    "Ctrl": ["Ctrl"],
                    "Shift": ["LShift", "RShift"],
                    "Alt": ["Alt"],
                    "Win": ["Win"]
                }

                allowed_all = (
                    allowed_keys |
                    set(modifier_keys.get(active_modifier, []))
                )

                if detected_key not in allowed_all:
                    detected_key = None

            if detected_key is not None:
                process_key(detected_key)
            else:
                reset_key_state()

            cv2.putText(
                frame,
                "KEYBOARD AREA",
                (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )

    else:
        reset_key_state()
        smoothed_mouse_x = None
        smoothed_mouse_y = None

    # 키보드 오버레이 그리기
    draw_keyboard_overlay(
        frame,
        KEY_MAP,
        detected_key
    )

    # 창은 이것 하나만 출력
    cv2.imshow("Laser Keyboard", frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break


cap.release()
cv2.destroyAllWindows()