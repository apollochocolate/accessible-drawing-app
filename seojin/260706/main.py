"""레이저 마우스 + 얼굴 제스처 제어 실행 파일.

실행:
    python main.py
"""

import time
from collections import deque

import cv2
import mediapipe as mp
import numpy as np
import pyautogui

from config import (
    ACTION_COOLDOWN,
    CAMERA_BACKEND,
    FACE_CAMERA_INDEX,
    FACE_GESTURE_ALWAYS_ON_FOR_TEST,
    GESTURE_DISTANCE_THRESHOLD,
    GESTURE_MARGIN,
    HSV_V_MIN,
    JUMP_THRESHOLD,
    LASER_CAMERA_INDEX,
    MIN_CURRENT_GESTURE_STRENGTH,
    MIN_LASER_SCORE,
    MIN_NEUTRAL_CHANGE,
    MOUSE_DEAD_ZONE,
    MOVE_THRESHOLD,
    RED_DIFF,
    R_MIN,
    SMOOTHING_ALPHA,
    STOP_DELAY,
    STRONG_GESTURE_MARGIN,
    STRONG_GESTURE_STRENGTH,
    TEST_STABLE_FRAMES,
)
from face_gesture import (
    capture_runtime_neutral,
    create_face_landmarker,
    find_gesture,
    make_face_vector,
    normalize_match_vector,
    vector_delta,
    vector_magnitude,
)
from gesture_server import start_gesture_save_server, wait_for_gesture_settings
from laser_tracker import camera_to_screen, detect_laser
from mouse_actions import execute_mouse_action

x_history = deque(maxlen=5)
y_history = deque(maxlen=5)


def main():
    settings = wait_for_gesture_settings()

    print()
    print("모든 제스처 설정이 저장되었습니다.")
    print("브라우저의 얼굴 설정 화면을 닫거나 카메라 사용을 멈춘 뒤 Enter를 누르세요.")
    input("준비되면 Enter: ")

    face_landmarker = create_face_landmarker()

    laser_cap = cv2.VideoCapture(LASER_CAMERA_INDEX, CAMERA_BACKEND)
    face_cap = cv2.VideoCapture(FACE_CAMERA_INDEX, CAMERA_BACKEND)

    if not laser_cap.isOpened():
        print("레이저 카메라를 열 수 없습니다.")
        print("LASER_CAMERA_INDEX를 0, 1, 2로 바꿔보세요.")
        return

    if not face_cap.isOpened():
        print("얼굴 카메라를 열 수 없습니다.")
        print("FACE_CAMERA_INDEX를 0, 1, 2로 바꿔보세요.")
        laser_cap.release()
        return

    runtime_neutral_vector, calibrated_ts = capture_runtime_neutral(face_cap, face_landmarker)
    neutral_vector = runtime_neutral_vector or settings["neutral"]["vector"]

    print("최종 레이저 + 얼굴 마우스 제어 시작")
    print("종료: q 또는 ESC")
    print(f"레이저 카메라 번호: {LASER_CAMERA_INDEX}")
    print(f"얼굴 카메라 번호: {FACE_CAMERA_INDEX}")
    print(f"레이저 기준: R_MIN={R_MIN}, RED_DIFF={RED_DIFF}, HSV_V_MIN={HSV_V_MIN}, MIN_LASER_SCORE={MIN_LASER_SCORE}")
    print(f"얼굴 테스트 모드: {FACE_GESTURE_ALWAYS_ON_FOR_TEST}")
    print("얼굴 인식 방식: 저장된 제스처 전체 비교 모드")
    print("사용 특징: 고개 좌우 회전/yaw, 좌우 기울임/roll, 숙임/pitch, 눈 감김, 입 벌림, blendshape")
    print(f"얼굴 기준: NEUTRAL>{MIN_NEUTRAL_CHANGE}, GESTURE_D<{GESTURE_DISTANCE_THRESHOLD}, MARGIN>{GESTURE_MARGIN}, STABLE={TEST_STABLE_FRAMES}")

    last_laser_x = None
    last_laser_y = None
    last_valid_laser_x = None
    last_valid_laser_y = None

    smoothed_screen_x = None
    smoothed_screen_y = None

    last_move_time = time.time()
    last_action_time = 0.0
    last_label = None
    stable_count = 0
    last_face_timestamp_ms = calibrated_ts

    try:
        while True:
            # ------------------------------------------
            # 1. 레이저 카메라 처리
            # ------------------------------------------
            ret_laser, laser_frame = laser_cap.read()

            if not ret_laser:
                print("레이저 카메라 프레임을 읽을 수 없습니다.")
                continue

            laser_h, laser_w = laser_frame.shape[:2]
            best_candidate = detect_laser(
                laser_frame,
                prefer_point=(last_valid_laser_x, last_valid_laser_y)
            )

            laser_detected = False
            jump_ignored = False

            if best_candidate is not None:
                laser_detected = True

                raw_x = best_candidate["x"]
                raw_y = best_candidate["y"]

                x_history.append(raw_x)
                y_history.append(raw_y)

                laser_x = int(np.median(x_history))
                laser_y = int(np.median(y_history))

                if last_valid_laser_x is not None and last_valid_laser_y is not None:
                    jump = (
                        (laser_x - last_valid_laser_x) ** 2 +
                        (laser_y - last_valid_laser_y) ** 2
                    ) ** 0.5

                    if jump > JUMP_THRESHOLD:
                        jump_ignored = True
                    else:
                        last_valid_laser_x = laser_x
                        last_valid_laser_y = laser_y
                else:
                    last_valid_laser_x = laser_x
                    last_valid_laser_y = laser_y

                if not jump_ignored:
                    screen_x, screen_y = camera_to_screen(
                        laser_x,
                        laser_y,
                        laser_w,
                        laser_h
                    )

                    if last_laser_x is not None and last_laser_y is not None:
                        diff = (
                            (laser_x - last_laser_x) ** 2 +
                            (laser_y - last_laser_y) ** 2
                        ) ** 0.5

                        if diff > MOVE_THRESHOLD:
                            last_move_time = time.time()
                    else:
                        last_move_time = time.time()

                    last_laser_x = laser_x
                    last_laser_y = laser_y

                    if smoothed_screen_x is None or smoothed_screen_y is None:
                        smoothed_screen_x = screen_x
                        smoothed_screen_y = screen_y
                    else:
                        smoothed_screen_x = int(
                            smoothed_screen_x * (1 - SMOOTHING_ALPHA) +
                            screen_x * SMOOTHING_ALPHA
                        )
                        smoothed_screen_y = int(
                            smoothed_screen_y * (1 - SMOOTHING_ALPHA) +
                            screen_y * SMOOTHING_ALPHA
                        )

                    current_mouse_x, current_mouse_y = pyautogui.position()
                    mouse_diff = (
                        (smoothed_screen_x - current_mouse_x) ** 2 +
                        (smoothed_screen_y - current_mouse_y) ** 2
                    ) ** 0.5

                    if mouse_diff > MOUSE_DEAD_ZONE:
                        pyautogui.moveTo(smoothed_screen_x, smoothed_screen_y)

                    cv2.putText(
                        laser_frame,
                        f"Mouse ({smoothed_screen_x}, {smoothed_screen_y})",
                        (30, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 255),
                        2
                    )

                    cv2.putText(
                        laser_frame,
                        f"area={best_candidate.get('area', 0):.0f} wh={best_candidate.get('w', 0)}x{best_candidate.get('h', 0)} score={best_candidate.get('score', 0):.0f} red={best_candidate.get('red_strength', 0):.0f} v={best_candidate.get('v', 0):.0f}",
                        (30, 110),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 255),
                        2
                    )

                cv2.circle(laser_frame, (laser_x, laser_y), 10, (0, 255, 0), 2)
                cv2.putText(
                    laser_frame,
                    f"Laser ({laser_x}, {laser_y})",
                    (laser_x + 15, laser_y - 15),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

                if jump_ignored:
                    cv2.putText(
                        laser_frame,
                        "Jump ignored",
                        (30, 110),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 0, 255),
                        2
                    )

            else:
                x_history.clear()
                y_history.clear()

                last_laser_x = None
                last_laser_y = None
                last_valid_laser_x = None
                last_valid_laser_y = None
                smoothed_screen_x = None
                smoothed_screen_y = None

                cv2.putText(
                    laser_frame,
                    "Laser not detected",
                    (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2
                )

            stopped_time = time.time() - last_move_time

            # v10: 레이저가 움직일 때만 얼굴 제스처를 끕니다.
            # 레이저가 아예 없으면 얼굴 제스처는 켜둡니다.
            if FACE_GESTURE_ALWAYS_ON_FOR_TEST:
                face_gesture_allowed = True
                laser_status_text = "Face gesture ON (test)"
            elif not laser_detected:
                face_gesture_allowed = True
                laser_status_text = "No laser: Face gesture ON"
            elif stopped_time > STOP_DELAY:
                face_gesture_allowed = True
                laser_status_text = "Laser stopped: Face gesture ON"
            else:
                face_gesture_allowed = False
                laser_status_text = "Laser moving: Face gesture OFF"

            if face_gesture_allowed:
                cv2.putText(
                    laser_frame,
                    laser_status_text,
                    (30, 75),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )
            else:
                cv2.putText(
                    laser_frame,
                    laser_status_text,
                    (30, 75),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2
                )
                last_label = None
                stable_count = 0

            # ------------------------------------------
            # 2. 얼굴 카메라 처리
            # ------------------------------------------
            ret_face, face_frame = face_cap.read()

            if ret_face:
                face_rgb = cv2.cvtColor(face_frame, cv2.COLOR_BGR2RGB)
                face_rgb = np.ascontiguousarray(face_rgb)
                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=face_rgb
                )

                timestamp_ms = int(time.time() * 1000)
                if timestamp_ms <= last_face_timestamp_ms:
                    timestamp_ms = last_face_timestamp_ms + 1
                last_face_timestamp_ms = timestamp_ms

                face_result = face_landmarker.detect_for_video(mp_image, timestamp_ms)
                current_vector = make_face_vector(face_result)

                if not face_gesture_allowed:
                    face_text = "Face gesture OFF"
                    color = (0, 0, 255)

                elif not current_vector:
                    face_text = "Face not detected"
                    color = (0, 0, 255)
                    last_label = None
                    stable_count = 0

                else:
                    current_delta = vector_delta(current_vector, neutral_vector)
                    current_match_delta = normalize_match_vector(current_delta)
                    neutral_change = vector_magnitude(current_match_delta)

                    # v12: 중립이면 아무 제스처로도 판단하지 않습니다.
                    # 그 외에는 저장된 모든 제스처를 같은 방식으로 비교합니다.
                    if not current_match_delta or neutral_change < MIN_NEUTRAL_CHANGE:
                        yaw = current_vector.get("__head_yaw", 0.0) - neutral_vector.get("__head_yaw", 0.0)
                        roll = current_vector.get("__head_roll", 0.0) - neutral_vector.get("__head_roll", 0.0)
                        pitch = current_vector.get("__head_pitch_nose", 0.0) - neutral_vector.get("__head_pitch_nose", 0.0)
                        face_text = f"Neutral n={neutral_change:.3f} yaw={yaw:.3f} roll={roll:.3f} pitch={pitch:.3f}"
                        color = (255, 255, 255)
                        last_label = None
                        stable_count = 0
                    else:
                        best, second = find_gesture(current_delta, settings)

                        if not best:
                            face_text = f"No gesture n={neutral_change:.3f}"
                            color = (255, 255, 255)
                            last_label = None
                            stable_count = 0
                        else:
                            margin = (second["distance"] if second else float("inf")) - best["distance"]
                            detected_by_distance = (
                                best["distance"] <= GESTURE_DISTANCE_THRESHOLD and
                                margin >= GESTURE_MARGIN and
                                best.get("current_strength", 0.0) >= MIN_CURRENT_GESTURE_STRENGTH
                            )

                            detected_by_strong_gesture = (
                                best.get("current_strength", 0.0) >= STRONG_GESTURE_STRENGTH and
                                margin >= STRONG_GESTURE_MARGIN and
                                neutral_change >= MIN_NEUTRAL_CHANGE
                            )

                            detected = detected_by_distance or detected_by_strong_gesture

                            if not detected:
                                keys_preview = ",".join(best.get("signature_keys", [])[:3])
                                face_text = (
                                    f"Closest: {best['label']} "
                                    f"d={best['distance']:.3f} m={margin:.3f} "
                                    f"c={best.get('current_strength', 0.0):.3f} n={neutral_change:.3f} "
                                    f"[{keys_preview}]"
                                )
                                color = (255, 255, 255)
                                last_label = None
                                stable_count = 0
                            else:
                                if last_label == best["id"]:
                                    stable_count += 1
                                else:
                                    last_label = best["id"]
                                    stable_count = 1

                                if stable_count >= TEST_STABLE_FRAMES:
                                    face_text = f"Detected: {best['label']}"
                                    color = (0, 255, 0)

                                    now = time.time()
                                    if now - last_action_time > ACTION_COOLDOWN:
                                        execute_mouse_action(best["id"])
                                        last_action_time = now
                                        stable_count = 0
                                        last_label = None
                                else:
                                    face_text = f"Checking: {best['label']} {stable_count}/{TEST_STABLE_FRAMES}"
                                    color = (0, 255, 255)

                cv2.putText(
                    face_frame,
                    face_text,
                    (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    color,
                    2
                )

                cv2.imshow("Face Gesture Control", face_frame)

            cv2.imshow("Laser Mouse Control", laser_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                print("종료합니다.")
                break

    except pyautogui.FailSafeException:
        print("마우스 이동 중 예외가 발생했습니다. 계속 실행합니다.")

    finally:
        laser_cap.release()
        face_cap.release()
        cv2.destroyAllWindows()
        print("카메라가 꺼졌습니다.")


if __name__ == "__main__":
    start_gesture_save_server()
    main()
