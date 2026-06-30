"""
main_combined_split.py

실행 파일.

v3 흐름은 예전에 만들었던 final_laser_face_mouse_auto_save_v13_click_fix.py와 동일합니다.
1) Python 실행
2) gestures.json이 없으면 HTML 저장을 기다림
3) 모든 제스처가 저장되면 Enter 대기
4) Enter를 누르면 카메라 2개가 켜짐
5) 화면에는 키보드/마우스 영역이 합쳐진 창 하나만 표시됨

역할
- 레이저가 구분선 위에 있으면 키보드 영역: 실제 키 입력
- 레이저가 구분선 아래에 있으면 마우스 영역: 실제 커서 이동
- 얼굴 제스처는 내부 얼굴 카메라로 인식해서 클릭/우클릭/더블클릭/스크롤 실행
"""

import time
from collections import deque

import cv2
import numpy as np
import pyautogui

from config_combined import (
    LASER_CAMERA_INDEX,
    FACE_CAMERA_INDEX,
    CAMERA_BACKEND,
    WIN_W,
    WIN_H,
    MOUSE_ZONE_Y,
    MOVE_THRESHOLD,
    STOP_DELAY,
    JUMP_THRESHOLD,
    SMOOTHING_ALPHA,
    MOUSE_DEAD_ZONE,
    FACE_GESTURE_ALWAYS_ON_FOR_TEST,
)
from gesture_store import start_gesture_save_server, wait_for_gesture_settings
from face_features import (
    create_face_landmarker,
    capture_runtime_neutral,
    frame_to_face_vector,
    FaceGestureRecognizer,
)
from laser_tracker import detect_laser
from input_actions import (
    KeyboardInputController,
    mouse_zone_to_screen,
    move_mouse_to,
    execute_mouse_action,
)
from keyboard_layout import KEY_MAP
from renderer import draw_keyboard_overlay


def get_key_at_layout(x, y):
    for name, (x1, y1, x2, y2) in KEY_MAP.items():
        if x1 <= x <= x2 and y1 <= y <= y2:
            return name
    return None


def open_camera(index, name):
    cap = cv2.VideoCapture(index, CAMERA_BACKEND)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIN_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WIN_H)

    for _ in range(10):
        cap.read()

    if not cap.isOpened():
        raise RuntimeError(f"{name} 카메라를 열 수 없습니다. 카메라 번호를 확인하세요: {index}")
    return cap


def put_status(frame, text, y, color=(255, 255, 255)):
    cv2.putText(
        frame,
        text,
        (10, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        color,
        2,
    )


def main():
    # 1) v13 방식: 제스처 설정이 저장될 때까지 카메라를 켜지 않고 기다림
    settings = wait_for_gesture_settings()

    print()
    print("모든 제스처 설정이 저장되었습니다.")
    print("브라우저의 얼굴 설정 화면을 닫거나 카메라 사용을 멈춘 뒤 Enter를 누르세요.")
    print("Enter를 누르면 레이저 키보드/마우스 창 하나만 뜨고, 얼굴 카메라는 내부적으로만 사용됩니다.")
    input("준비되면 Enter: ")

    # 2) Enter 이후 카메라와 얼굴 모델 실행
    face_landmarker = create_face_landmarker()

    print("카메라를 엽니다.")
    print(f"레이저 카메라 번호: {LASER_CAMERA_INDEX}")
    print(f"얼굴 카메라 번호: {FACE_CAMERA_INDEX}")

    laser_cap = open_camera(LASER_CAMERA_INDEX, "레이저")
    face_cap = open_camera(FACE_CAMERA_INDEX, "얼굴")

    # 얼굴 카메라는 켜지지만 별도 창은 띄우지 않고, 내부적으로 중립만 다시 잡음
    runtime_neutral, last_face_timestamp_ms = capture_runtime_neutral(face_cap, face_landmarker)
    neutral_vector = runtime_neutral or settings["neutral"]["vector"]
    face_recognizer = FaceGestureRecognizer(settings, neutral_vector)
    keyboard = KeyboardInputController()

    x_history = deque(maxlen=5)
    y_history = deque(maxlen=5)

    last_laser_x = None
    last_laser_y = None
    last_valid_laser_x = None
    last_valid_laser_y = None
    smoothed_screen_x = None
    smoothed_screen_y = None
    last_move_time = time.time()

    face_text = "Face ready"
    face_color = (255, 255, 255)

    print("실행 중...")
    print("q 또는 ESC: 종료")
    print("구분선 위: 키보드 영역")
    print("구분선 아래: 마우스 이동 영역")
    print("얼굴 제스처: 클릭/우클릭/더블클릭/스크롤")
    print("표시 창: Laser Keyboard Mouse 하나만 사용")

    try:
        while True:
            # ------------------------------------------
            # 1. 레이저 카메라: 키보드/마우스 영역 처리
            # ------------------------------------------
            ret_laser, laser_frame = laser_cap.read()
            if not ret_laser or laser_frame is None or laser_frame.size == 0:
                laser_frame = np.zeros((WIN_H, WIN_W, 3), dtype=np.uint8)

            laser_frame = cv2.resize(laser_frame, (WIN_W, WIN_H))
            # 좌우가 반대로 느껴지면 아래 줄 주석 해제
            # laser_frame = cv2.flip(laser_frame, 1)

            candidate = detect_laser(
                laser_frame,
                prefer_point=(last_valid_laser_x, last_valid_laser_y),
            )

            detected_key = None
            laser_detected = candidate is not None
            laser_in_mouse_zone = False

            if laser_detected:
                raw_x = candidate["x"]
                raw_y = candidate["y"]

                x_history.append(raw_x)
                y_history.append(raw_y)
                laser_x = int(np.median(x_history))
                laser_y = int(np.median(y_history))

                jump_ignored = False
                if last_valid_laser_x is not None and last_valid_laser_y is not None:
                    jump = ((laser_x - last_valid_laser_x) ** 2 + (laser_y - last_valid_laser_y) ** 2) ** 0.5
                    if jump > JUMP_THRESHOLD:
                        jump_ignored = True
                    else:
                        last_valid_laser_x = laser_x
                        last_valid_laser_y = laser_y
                else:
                    last_valid_laser_x = laser_x
                    last_valid_laser_y = laser_y

                if not jump_ignored:
                    cv2.circle(laser_frame, (laser_x, laser_y), 8, (0, 0, 255), -1)
                    cv2.circle(laser_frame, (laser_x, laser_y), 12, (255, 255, 255), 2)

                    laser_in_mouse_zone = laser_y >= MOUSE_ZONE_Y

                    if laser_in_mouse_zone:
                        keyboard.reset_hover()

                        if last_laser_x is not None and last_laser_y is not None:
                            diff = ((laser_x - last_laser_x) ** 2 + (laser_y - last_laser_y) ** 2) ** 0.5
                            if diff > MOVE_THRESHOLD:
                                last_move_time = time.time()
                        else:
                            last_move_time = time.time()

                        last_laser_x = laser_x
                        last_laser_y = laser_y

                        screen_x, screen_y = mouse_zone_to_screen(laser_x, laser_y)

                        if smoothed_screen_x is None or smoothed_screen_y is None:
                            smoothed_screen_x = screen_x
                            smoothed_screen_y = screen_y
                        else:
                            smoothed_screen_x = int(smoothed_screen_x * (1 - SMOOTHING_ALPHA) + screen_x * SMOOTHING_ALPHA)
                            smoothed_screen_y = int(smoothed_screen_y * (1 - SMOOTHING_ALPHA) + screen_y * SMOOTHING_ALPHA)

                        current_mouse_x, current_mouse_y = pyautogui.position()
                        mouse_diff = ((smoothed_screen_x - current_mouse_x) ** 2 + (smoothed_screen_y - current_mouse_y) ** 2) ** 0.5

                        if mouse_diff > MOUSE_DEAD_ZONE:
                            move_mouse_to(smoothed_screen_x, smoothed_screen_y)

                        put_status(laser_frame, "MOUSE AREA", 25, (0, 255, 255))

                    else:
                        smoothed_screen_x = None
                        smoothed_screen_y = None
                        last_laser_x = None
                        last_laser_y = None

                        detected_key = get_key_at_layout(laser_x, laser_y)
                        if detected_key is not None:
                            keyboard.process_key(detected_key)
                        else:
                            keyboard.reset_hover()

                        put_status(laser_frame, "KEYBOARD AREA", 25, (0, 255, 0))

                    cv2.putText(
                        laser_frame,
                        f"Laser ({laser_x}, {laser_y})",
                        (laser_x + 15, max(laser_y - 15, 15)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 0),
                        2,
                    )

                else:
                    put_status(laser_frame, "Jump ignored", 25, (0, 0, 255))

            else:
                x_history.clear()
                y_history.clear()
                last_laser_x = None
                last_laser_y = None
                last_valid_laser_x = None
                last_valid_laser_y = None
                smoothed_screen_x = None
                smoothed_screen_y = None
                keyboard.reset_hover()
                put_status(laser_frame, "Laser not detected", 25, (0, 0, 255))

            # 얼굴 제스처 허용 조건
            stopped_time = time.time() - last_move_time
            if FACE_GESTURE_ALWAYS_ON_FOR_TEST:
                face_gesture_allowed = True
                laser_status_text = "Face gesture ON (test)"
            elif not laser_detected:
                face_gesture_allowed = True
                laser_status_text = "No laser: Face gesture ON"
            elif laser_in_mouse_zone and stopped_time > STOP_DELAY:
                face_gesture_allowed = True
                laser_status_text = "Mouse stopped: Face gesture ON"
            else:
                face_gesture_allowed = False
                laser_status_text = "Laser/keyboard active: Face gesture OFF"

            put_status(
                laser_frame,
                laser_status_text,
                55,
                (0, 255, 0) if face_gesture_allowed else (0, 0, 255),
            )

            # ------------------------------------------
            # 2. 얼굴 카메라: 내부 인식만 수행, 별도 창은 띄우지 않음
            # ------------------------------------------
            ret_face, face_frame = face_cap.read()
            if ret_face:
                timestamp_ms = int(time.time() * 1000)
                if timestamp_ms <= last_face_timestamp_ms:
                    timestamp_ms = last_face_timestamp_ms + 1
                last_face_timestamp_ms = timestamp_ms

                current_vector = frame_to_face_vector(face_frame, face_landmarker, timestamp_ms)
                face_text, face_color, action_id = face_recognizer.update(current_vector, face_gesture_allowed)

                if action_id:
                    execute_mouse_action(action_id)

            else:
                face_text = "Face camera frame error"
                face_color = (0, 0, 255)

            # 키보드 오버레이와 얼굴 상태를 같은 창에 함께 표시
            draw_keyboard_overlay(laser_frame, KEY_MAP, detected_key)
            put_status(laser_frame, f"FACE: {face_text}", WIN_H - 20, face_color)

            cv2.imshow("Laser Keyboard Mouse", laser_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                print("종료합니다.")
                break

    finally:
        laser_cap.release()
        face_cap.release()
        cv2.destroyAllWindows()
        print("카메라가 꺼졌습니다.")


if __name__ == "__main__":
    start_gesture_save_server()
    main()
