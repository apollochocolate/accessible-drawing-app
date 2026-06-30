import cv2
import numpy as np
import pyautogui
import time
import threading
from collections import deque

from flask import Flask, request, jsonify
from flask_cors import CORS


# ==================================================
# Flask 서버 설정
# ==================================================
app = Flask(__name__)
CORS(app)


# ==================================================
# 카메라 / 레이저 설정
# ==================================================
LASER_CAMERA_INDEX = 1  # 안 되면 1, 2로 바꿔보기

# 레이저 인식 기준값
R_MIN = 120
RED_DIFF = 25

# 레이저 점 크기 조건
MIN_AREA = 1
MAX_AREA = 300
MAX_W_H = 50


# ==================================================
# 마우스 이동 보정 설정
# ==================================================
MOVE_THRESHOLD = 8
STOP_DELAY = 0.5

JUMP_THRESHOLD = 90
SMOOTHING_ALPHA = 0.25
MOUSE_DEAD_ZONE = 4

x_history = deque(maxlen=5)
y_history = deque(maxlen=5)

screen_w, screen_h = pyautogui.size()

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0


# ==================================================
# 얼굴 제스처 실행 제어
# ==================================================
face_gesture_allowed = False
state_lock = threading.Lock()

last_action_time = 0
ACTION_COOLDOWN = 0.8

running = True


# ==================================================
# 레이저 좌표 찾기
# ==================================================
def detect_laser(frame):
    b, g, r = cv2.split(frame)

    r_i = r.astype(np.int16)
    g_i = g.astype(np.int16)
    b_i = b.astype(np.int16)

    red_by_bgr = (
        (r_i > R_MIN) &
        (r_i > g_i + RED_DIFF) &
        (r_i > b_i + RED_DIFF)
    )

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    h_i = h.astype(np.int16)
    s_i = s.astype(np.int16)
    v_i = v.astype(np.int16)

    red_by_hsv = (
        ((h_i < 10) | (h_i > 170)) &
        (s_i > 40) &
        (v_i > 100)
    )

    laser_pixel = red_by_bgr | red_by_hsv
    mask = laser_pixel.astype(np.uint8) * 255
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

        x, y, w, h_box = cv2.boundingRect(contour)

        if w > MAX_W_H or h_box > MAX_W_H:
            continue

        ratio = w / h_box if h_box != 0 else 0

        if ratio < 0.3 or ratio > 3.0:
            continue

        M = cv2.moments(contour)

        if M["m00"] == 0:
            continue

        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])

        score = int(r[cy, cx]) + area

        if score > best_score:
            best_score = score
            best_candidate = {
                "x": cx,
                "y": cy,
                "area": area
            }

    return best_candidate, mask


# ==================================================
# 카메라 좌표 → 실제 화면 좌표
# ==================================================
def camera_to_screen(laser_x, laser_y, frame_w, frame_h):
    rel_x = laser_x / frame_w
    rel_y = laser_y / frame_h

    rel_x = max(0, min(1, rel_x))
    rel_y = max(0, min(1, rel_y))

    screen_x = int(rel_x * screen_w)
    screen_y = int(rel_y * screen_h)

    screen_x = max(0, min(screen_w - 1, screen_x))
    screen_y = max(0, min(screen_h - 1, screen_y))

    return screen_x, screen_y


# ==================================================
# 얼굴 제스처 허용 상태 변경
# ==================================================
def set_face_gesture_allowed(value):
    global face_gesture_allowed

    with state_lock:
        face_gesture_allowed = value


def get_face_gesture_allowed():
    with state_lock:
        return face_gesture_allowed


# ==================================================
# 실제 마우스 동작 실행
# ==================================================
def execute_mouse_action(action):
    global last_action_time

    now = time.time()

    if now - last_action_time < ACTION_COOLDOWN:
        return "cooldown"

    if action == "left_single":
        pyautogui.click()
        print("왼쪽 클릭 실행")

    elif action == "right_single":
        pyautogui.rightClick()
        print("오른쪽 클릭 실행")

    elif action == "left_double":
        pyautogui.doubleClick()
        print("왼쪽 더블클릭 실행")

    elif action == "scroll_up":
        pyautogui.scroll(5)
        print("스크롤 위 실행")

    elif action == "scroll_down":
        pyautogui.scroll(-5)
        print("스크롤 아래 실행")

    else:
        print("알 수 없는 제스처:", action)
        return "unknown action"

    last_action_time = now
    return "ok"


# ==================================================
# index.html에서 제스처 받는 API
# ==================================================
@app.route("/gesture", methods=["POST"])
def receive_gesture():
    data = request.get_json()
    action = data.get("action")

    print("웹에서 받은 제스처:", action)

    if not get_face_gesture_allowed():
        print("레이저가 움직이는 중이거나 레이저가 안 잡혀서 제스처 무시")
        return jsonify({
            "status": "ignored",
            "reason": "laser moving or not detected"
        })

    result = execute_mouse_action(action)

    return jsonify({
        "status": result,
        "action": action
    })


@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "server": "running",
        "face_gesture_allowed": get_face_gesture_allowed()
    })


# ==================================================
# 레이저 마우스 제어 루프
# ==================================================
def laser_mouse_loop():
    global running

    last_laser_x = None
    last_laser_y = None
    last_valid_laser_x = None
    last_valid_laser_y = None

    smoothed_screen_x = None
    smoothed_screen_y = None

    last_move_time = time.time()

    cap = cv2.VideoCapture(LASER_CAMERA_INDEX, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print("레이저용 카메라를 열 수 없습니다.")
        print("LASER_CAMERA_INDEX를 0, 1, 2로 바꿔보세요.")
        set_face_gesture_allowed(False)
        return

    print("레이저 마우스 제어 시작")
    print("종료하려면 Laser Mouse Control 창에서 q 또는 ESC를 누르세요.")

    try:
        while running:
            ret, frame = cap.read()

            if not ret:
                print("레이저 카메라 프레임을 읽을 수 없습니다.")
                set_face_gesture_allowed(False)
                continue

            # 움직임이 좌우 반대로 느껴지면 아래 줄 주석 해제
            # frame = cv2.flip(frame, 1)

            frame_h, frame_w = frame.shape[:2]

            best_candidate, mask = detect_laser(frame)

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

                # =========================
                # 큰 튐 제거
                # =========================
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
                        frame_w,
                        frame_h
                    )

                    # =========================
                    # 레이저 이동 여부 확인
                    # =========================
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

                    # =========================
                    # 마우스 좌표 부드럽게 보정
                    # =========================
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
                        try:
                            pyautogui.moveTo(smoothed_screen_x, smoothed_screen_y)
                        except pyautogui.FailSafeException:
                            print("PyAutoGUI fail-safe 작동. 프로그램을 종료합니다.")
                            running = False
                            break

                    cv2.putText(
                        frame,
                        f"Mouse ({smoothed_screen_x}, {smoothed_screen_y})",
                        (30, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 255),
                        2
                    )

                cv2.circle(frame, (laser_x, laser_y), 10, (0, 255, 0), 2)

                cv2.putText(
                    frame,
                    f"Laser ({laser_x}, {laser_y})",
                    (laser_x + 15, laser_y - 15),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

                if jump_ignored:
                    cv2.putText(
                        frame,
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

            # =========================
            # 레이저 정지 상태일 때만 얼굴 제스처 허용
            # =========================
            stopped_time = time.time() - last_move_time

            if laser_detected and stopped_time > STOP_DELAY:
                set_face_gesture_allowed(True)

                cv2.putText(
                    frame,
                    "Mouse stopped: Face gesture ON",
                    (30, 75),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )

            else:
                set_face_gesture_allowed(False)

                cv2.putText(
                    frame,
                    "Mouse moving: Face gesture OFF",
                    (30, 75),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2
                )

            cv2.imshow("Laser Mouse Control", frame)

            # 마스크 확인하고 싶으면 주석 해제
            # cv2.imshow("Mask", mask)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q") or key == 27:
                print("종료합니다.")
                running = False
                break

    finally:
        set_face_gesture_allowed(False)
        cap.release()
        cv2.destroyAllWindows()
        print("레이저 카메라가 꺼졌습니다.")


# ==================================================
# 실행
# ==================================================
if __name__ == "__main__":
    laser_thread = threading.Thread(target=laser_mouse_loop, daemon=True)
    laser_thread.start()

    print("Python 제스처 서버 시작")
    print("주소: http://127.0.0.1:5000")

    app.run(host="127.0.0.1", port=5000, debug=False)