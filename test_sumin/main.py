"""
팀 통합 실행 파일.

최대한 기존 파일을 유지하고 main.py에서 연결만 합니다.
- 친구 작업: keyboard_layout.py / renderer.py / InputController 기반 키보드 선택
- 기존 사용자 작업: laser_tracker.py 기반 레이저 마우스 + 얼굴 제스처 인식

동작
1) 레이저가 구분선 위: 키보드 hover
2) 얼굴 left_single: hover 중인 키 입력
3) 레이저가 구분선 아래: 실제 마우스 이동
4) 얼굴 제스처: 클릭 / 우클릭 / 더블클릭 / 스크롤
5) 화면에는 Face Gesture Control 창과 Laser Keyboard 창을 각각 표시
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
    JUMP_REACQUIRE_FRAMES,
    SMOOTHING_ALPHA,
    MOUSE_DEAD_ZONE,
    FACE_GESTURE_ALWAYS_ON_FOR_TEST,
)
from keyboard_listener import start_keyboard_listener
from keyboard_layout import KEY_MAP
from renderer_updated import draw_keyboard_overlay
from input_controller import InputController

from gesture_store import start_gesture_save_server, wait_for_gesture_settings
from face_features import (
    create_face_landmarker,
    capture_runtime_neutral,
    frame_to_face_vector,
    FaceGestureRecognizer,
)
from laser_tracker import detect_laser
from mouse_controller import mouse_zone_to_screen, move_mouse_to, execute_mouse_action
from stt_voice_click import VoiceController


# keyboard_layout.py에서 음성 키 이름을 "Voice"로 추가하는 것을 권장합니다.
VOICE_KEY_NAMES = {"Voice", "VOICE", "음성", "STT"}


def get_key_at(x, y):
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
        raise RuntimeError(f"{name} 카메라를 열 수 없습니다. 카메라 번호: {index}")
    return cap


def put_status(frame, text, y, color=(255, 255, 255)):
    cv2.putText(
        frame,
        text,
        (10, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        color,
        2,
    )


def route_face_action(action_id, zone, controller, detected_key, voice_controller):
    """얼굴 제스처 결과를 키보드·음성·마우스 동작으로 전달합니다."""
    if not action_id:
        return

    # 키보드의 음성 키는 left_single 제스처로만 ON/OFF 한다.
    if zone == "keyboard":
        if action_id == "left_single":
            if detected_key in VOICE_KEY_NAMES:
                if voice_controller.toggle():
                    print("[음성] 음성 제어를 시작합니다.")
                else:
                    print("[음성] 음성 제어를 종료 요청했습니다.")
                controller.update_hover(None)  # Voice라는 글자가 OS에 입력되지 않게 차단
            else:
                controller.left_click()
        return

    # 음성 명령도 이 함수와 같은 execute_mouse_action()으로 연결된다.
    execute_mouse_action(action_id)


def main():
    # v13과 같은 흐름: 제스처 저장 확인 → Enter → 카메라 실행
    settings = wait_for_gesture_settings()

    print()
    print("모든 제스처 설정이 저장되었습니다.")
    print("브라우저의 얼굴 설정 화면을 닫거나 카메라 사용을 멈춘 뒤 Enter를 누르세요.")
    input("준비되면 Enter: ")

    face_landmarker = create_face_landmarker()

    print(f"레이저 카메라: {LASER_CAMERA_INDEX}")
    print(f"얼굴 카메라: {FACE_CAMERA_INDEX}")

    laser_cap = open_camera(LASER_CAMERA_INDEX, "레이저")
    face_cap = open_camera(FACE_CAMERA_INDEX, "얼굴")

    runtime_neutral, last_face_timestamp_ms = capture_runtime_neutral(
        face_cap,
        face_landmarker,
    )
    neutral_vector = runtime_neutral or settings["neutral"]["vector"]
    face_recognizer = FaceGestureRecognizer(settings, neutral_vector)

    controller = InputController()
    # STT가 기존 마우스 제스처와 동일한 실행 함수를 사용하도록 연결
    voice_controller = VoiceController(execute_mouse_action)
    start_keyboard_listener(controller)

    x_history = deque(maxlen=5)
    y_history = deque(maxlen=5)

    last_laser_x = None
    last_laser_y = None
    last_valid_laser_x = None
    last_valid_laser_y = None
    jump_reject_count = 0

    smoothed_screen_x = None
    smoothed_screen_y = None
    last_move_time = time.time()

    current_zone = "none"
    detected_key = None
    face_text = "Face ready"
    face_color = (255, 255, 255)

    print("실행 중...")
    print("구분선 위: 키보드 영역")
    print("구분선 아래: 마우스 영역")
    print("키보드 영역 + 얼굴 left click: 현재 글자 입력")
    print("Voice 키 + 얼굴 left click: 음성 제어 ON/OFF")
    print("마우스 영역 + 얼굴 제스처: 클릭/우클릭/더블클릭/스크롤")
    print("q 또는 ESC: 종료")

    try:
        while True:
            # ==================================================
            # 1. 레이저 카메라: 키보드 / 마우스 영역 판단
            # ==================================================
            ret_laser, frame = laser_cap.read()
            if not ret_laser or frame is None or frame.size == 0:
                frame = np.zeros((WIN_H, WIN_W, 3), dtype=np.uint8)

            frame = cv2.resize(frame, (WIN_W, WIN_H))

            candidate = detect_laser(
                frame,
                prefer_point=(last_valid_laser_x, last_valid_laser_y),
            )

            laser_detected = candidate is not None
            detected_key = None
            current_zone = "none"

            if candidate is not None:
                x_history.append(candidate["x"])
                y_history.append(candidate["y"])
                laser_x = int(np.median(x_history))
                laser_y = int(np.median(y_history))

                accept_position = True
                if last_valid_laser_x is not None and last_valid_laser_y is not None:
                    jump = (
                        (laser_x - last_valid_laser_x) ** 2
                        + (laser_y - last_valid_laser_y) ** 2
                    ) ** 0.5

                    if jump > JUMP_THRESHOLD:
                        jump_reject_count += 1
                        if jump_reject_count < JUMP_REACQUIRE_FRAMES:
                            accept_position = False
                        else:
                            # 새 위치에 계속 레이저가 있으면 재획득
                            last_valid_laser_x = laser_x
                            last_valid_laser_y = laser_y
                            jump_reject_count = 0
                    else:
                        last_valid_laser_x = laser_x
                        last_valid_laser_y = laser_y
                        jump_reject_count = 0
                else:
                    last_valid_laser_x = laser_x
                    last_valid_laser_y = laser_y

                if accept_position:
                    cv2.circle(frame, (laser_x, laser_y), 8, (0, 0, 255), -1)
                    cv2.circle(frame, (laser_x, laser_y), 12, (255, 255, 255), 2)

                    # ------------------------------------------
                    # 구분선 위: 친구 키보드 로직 유지
                    # ------------------------------------------
                    if laser_y < MOUSE_ZONE_Y:
                        current_zone = "keyboard"
                        detected_key = get_key_at(laser_x, laser_y)
                        controller.update_hover(detected_key)

                        smoothed_screen_x = None
                        smoothed_screen_y = None
                        last_laser_x = None
                        last_laser_y = None

                        put_status(frame, "KEYBOARD AREA", 25, (0, 255, 0))

                    # ------------------------------------------
                    # 구분선 아래: 기존 레이저 마우스 로직
                    # ------------------------------------------
                    else:
                        current_zone = "mouse"
                        controller.update_hover(None)

                        if last_laser_x is not None and last_laser_y is not None:
                            diff = (
                                (laser_x - last_laser_x) ** 2
                                + (laser_y - last_laser_y) ** 2
                            ) ** 0.5
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
                            smoothed_screen_x = int(
                                smoothed_screen_x * (1 - SMOOTHING_ALPHA)
                                + screen_x * SMOOTHING_ALPHA
                            )
                            smoothed_screen_y = int(
                                smoothed_screen_y * (1 - SMOOTHING_ALPHA)
                                + screen_y * SMOOTHING_ALPHA
                            )

                        current_mouse_x, current_mouse_y = pyautogui.position()
                        mouse_diff = (
                            (smoothed_screen_x - current_mouse_x) ** 2
                            + (smoothed_screen_y - current_mouse_y) ** 2
                        ) ** 0.5

                        if mouse_diff > MOUSE_DEAD_ZONE:
                            move_mouse_to(smoothed_screen_x, smoothed_screen_y)

                        put_status(frame, "MOUSE AREA", 25, (0, 255, 255))

                    cv2.putText(
                        frame,
                        f"Laser ({laser_x}, {laser_y})",
                        (laser_x + 15, max(laser_y - 15, 15)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (0, 255, 0),
                        2,
                    )
                else:
                    controller.update_hover(None)
                    put_status(frame, "Laser position checking", 25, (0, 0, 255))

            else:
                x_history.clear()
                y_history.clear()
                last_laser_x = None
                last_laser_y = None
                last_valid_laser_x = None
                last_valid_laser_y = None
                jump_reject_count = 0
                smoothed_screen_x = None
                smoothed_screen_y = None
                controller.update_hover(None)
                put_status(frame, "Laser not detected", 25, (0, 0, 255))

            # ==================================================
            # 2. 얼굴 제스처 허용 조건
            # ==================================================
            stopped_time = time.time() - last_move_time

            if FACE_GESTURE_ALWAYS_ON_FOR_TEST:
                face_allowed = True
            elif current_zone == "keyboard":
                # 키보드에서는 레이저로 키를 가리킨 채 얼굴 클릭해야 하므로 항상 ON
                face_allowed = True
            elif current_zone == "mouse":
                # 마우스 이동 중에는 OFF, 멈춘 뒤 ON
                face_allowed = stopped_time > STOP_DELAY
            else:
                # 레이저가 없으면 현재 커서 위치에 얼굴 제스처 사용 가능
                face_allowed = True

            # ==================================================
            # 3. 얼굴 카메라: 얼굴 제스처 처리 + 별도 얼굴 창 표시
            # ==================================================
            ret_face, face_frame = face_cap.read()
            if ret_face:
                timestamp_ms = int(time.time() * 1000)
                if timestamp_ms <= last_face_timestamp_ms:
                    timestamp_ms = last_face_timestamp_ms + 1
                last_face_timestamp_ms = timestamp_ms

                current_vector = frame_to_face_vector(
                    face_frame,
                    face_landmarker,
                    timestamp_ms,
                )
                face_text, face_color, action_id = face_recognizer.update(
                    current_vector,
                    face_allowed,
                )

                route_face_action(
                    action_id, current_zone, controller, detected_key, voice_controller
                )

                # 얼굴 인식 상태는 얼굴 화면에 표시
                cv2.putText(
                    face_frame,
                    face_text,
                    (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.75,
                    face_color,
                    2,
                )
                cv2.imshow("Face Gesture Control", face_frame)
            else:
                face_text = "Face camera frame error"
                face_color = (0, 0, 255)

            # ==================================================
            # 4. 친구 키보드 + 마우스 영역 화면 표시
            # ==================================================
            put_status(frame, voice_controller.last_message, WIN_H - 15, (0, 255, 0) if voice_controller.is_running else (180, 180, 180))
            draw_keyboard_overlay(frame, KEY_MAP, detected_key)
            cv2.imshow("Laser Keyboard", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                break

    finally:
        voice_controller.stop()
        laser_cap.release()
        face_cap.release()
        cv2.destroyAllWindows()
        print("카메라가 꺼졌습니다.")


if __name__ == "__main__":
    start_gesture_save_server()
    main()
