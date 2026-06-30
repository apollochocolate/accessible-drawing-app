"""
final_laser_face_mouse.py

역할
1) 레이저 카메라로 실제 마우스 커서 이동
2) 얼굴 카메라로 저장된 제스처를 인식
3) 클릭 / 우클릭 / 더블클릭 / 스크롤 실행

준비물
- gesture_settings_auto_save.html : 얼굴 제스처 저장용 화면
- gestures.json : HTML에서 저장하면 Python이 같은 폴더에 자동 생성
- face_landmarker.task : MediaPipe 얼굴 인식 모델 파일

설치
pip install opencv-python numpy pyautogui mediapipe
"""

import json
import os
import time
import urllib.request
import threading
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np
import pyautogui
import mediapipe as mp

try:
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
except Exception as e:
    print("MediaPipe를 불러오지 못했습니다.")
    print("설치 명령어: pip install mediapipe")
    raise e


# ==================================================
# 파일 설정
# ==================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GESTURE_FILE = os.path.join(BASE_DIR, "gestures.json")
MODEL_FILE = os.path.join(BASE_DIR, "face_landmarker.task")
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"

# HTML 설정 화면이 제스처를 자동 저장할 때 사용할 주소
SETTINGS_SERVER_HOST = "127.0.0.1"
SETTINGS_SERVER_PORT = 5000


# ==================================================
# 카메라 설정
# ==================================================
# 보통 노트북 내장캠은 0번입니다.
# 레이저용 외장 카메라와 얼굴용 웹캠을 각각 다르게 지정해야 합니다.
LASER_CAMERA_INDEX = 2
FACE_CAMERA_INDEX = 0

# Windows에서는 CAP_DSHOW가 안정적인 경우가 많습니다.
# Mac이면 cv2.CAP_AVFOUNDATION으로 바꿔보세요.
CAMERA_BACKEND = cv2.CAP_DSHOW
# CAMERA_BACKEND = cv2.CAP_AVFOUNDATION


# ==================================================
# 레이저 인식 기준값
# ==================================================
R_MIN = 120
RED_DIFF = 25

MIN_AREA = 1
MAX_AREA = 300
MAX_W_H = 50

x_history = deque(maxlen=5)
y_history = deque(maxlen=5)

MOVE_THRESHOLD = 8
STOP_DELAY = 0.5

JUMP_THRESHOLD = 90
SMOOTHING_ALPHA = 0.25
MOUSE_DEAD_ZONE = 4


# ==================================================
# 얼굴 제스처 인식 기준값
# HTML 설정 파일과 같은 기준으로 맞춤
# ==================================================
TEST_THRESHOLD = 0.23
TEST_MARGIN = 0.01
TEST_STABLE_FRAMES = 6
MIN_NEUTRAL_CHANGE = 0.035
ACTION_COOLDOWN = 0.8


# ==================================================
# PyAutoGUI 설정
# ==================================================
screen_w, screen_h = pyautogui.size()
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0


# ==================================================
# 제스처 설정 불러오기
# ==================================================
def load_gesture_settings():
    if not os.path.exists(GESTURE_FILE):
        raise FileNotFoundError(
            f"gestures.json 파일이 없습니다. 필요한 위치: {GESTURE_FILE}"
        )

    with open(GESTURE_FILE, "r", encoding="utf-8") as f:
        settings = json.load(f)

    if "neutral" not in settings or "vector" not in settings.get("neutral", {}):
        raise ValueError("gestures.json 안에 기본 중립 얼굴(neutral) 설정이 없습니다.")

    return settings


def save_gesture_settings(settings):
    with open(GESTURE_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


class GestureSaveHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path != "/gestures":
            self._send_json(404, {"status": "not_found"})
            return

        if not os.path.exists(GESTURE_FILE):
            self._send_json(200, {"status": "empty", "settings": {}})
            return

        try:
            with open(GESTURE_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
            self._send_json(200, {"status": "ok", "settings": settings})
        except Exception as e:
            self._send_json(500, {"status": "error", "message": str(e)})

    def do_POST(self):
        if self.path != "/save_gestures":
            self._send_json(404, {"status": "not_found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            settings = json.loads(body or "{}")

            if not isinstance(settings, dict):
                self._send_json(400, {"status": "error", "message": "settings must be object"})
                return

            save_gesture_settings(settings)
            self._send_json(200, {"status": "ok", "saved_to": GESTURE_FILE})
            print(f"제스처 설정 자동 저장 완료: {GESTURE_FILE}")
        except Exception as e:
            self._send_json(500, {"status": "error", "message": str(e)})

    def log_message(self, format, *args):
        # 기본 HTTP 로그를 줄이기 위해 비워둠
        return


def start_gesture_save_server():
    server = ThreadingHTTPServer(
        (SETTINGS_SERVER_HOST, SETTINGS_SERVER_PORT),
        GestureSaveHandler
    )

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print(f"제스처 자동 저장 서버 시작: http://{SETTINGS_SERVER_HOST}:{SETTINGS_SERVER_PORT}")
    print("gesture_settings_auto_save.html에서 저장하면 gestures.json이 자동 생성됩니다.")
    return server


def wait_for_gesture_settings():
    while True:
        try:
            return load_gesture_settings()
        except Exception as e:
            print("제스처 설정 대기 중:", e)
            print("HTML에서 기본 중립 얼굴과 필요한 제스처를 저장하세요. Ctrl+C로 종료할 수 있습니다.")
            time.sleep(2)


# ==================================================
# MediaPipe FaceLandmarker 생성
# ==================================================
def ensure_model_file():
    if os.path.exists(MODEL_FILE):
        return

    print("face_landmarker.task 모델 파일이 없어 자동 다운로드를 시도합니다.")

    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_FILE)
        print("face_landmarker.task 다운로드 완료")
    except Exception as e:
        raise FileNotFoundError(
            f"face_landmarker.task 모델 파일이 없습니다.\n"
            f"자동 다운로드에도 실패했습니다.\n"
            f"MediaPipe face_landmarker.task 파일을 직접 다운로드해서 이 Python 파일과 같은 폴더에 넣어주세요.\n"
            f"필요한 위치: {MODEL_FILE}"
        ) from e


def create_face_landmarker():
    ensure_model_file()

    base_options = python.BaseOptions(model_asset_path=MODEL_FILE)

    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=True,
    )

    return vision.FaceLandmarker.create_from_options(options)


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
# 얼굴 결과 → HTML에서 저장한 것과 같은 벡터로 변환
# ==================================================
def make_face_vector(result):
    vector = {}

    # 1) 얼굴 표정 blendshape 점수
    if result.face_blendshapes:
        for category in result.face_blendshapes[0]:
            vector[category.category_name] = float(category.score)

    # 2) 얼굴 랜드마크 기반 고개 움직임 특징
    landmarks = result.face_landmarks[0] if result.face_landmarks else None

    if landmarks:
        try:
            nose = landmarks[1]
            forehead = landmarks[10]
            chin = landmarks[152]
            left_eye = landmarks[33]
            right_eye = landmarks[263]

            eye_y = (left_eye.y + right_eye.y) / 2
            face_h = max(abs(chin.y - forehead.y), 0.001)

            vector["__head_pitch_1"] = float((nose.y - eye_y) / face_h)
            vector["__head_pitch_2"] = float((chin.y - eye_y) / face_h)
            vector["__head_z"] = float((nose.z or 0) / face_h)
        except Exception:
            pass

    # 3) 얼굴 자세 matrix
    if result.facial_transformation_matrixes:
        matrix = result.facial_transformation_matrixes[0]
        data = np.array(matrix).flatten()

        for i, value in enumerate(data):
            vector[f"__pose_{i}"] = float(value) * 0.15

    return vector if vector else None


# ==================================================
# 벡터 거리 계산
# ==================================================
def distance(a, b):
    if not a or not b:
        return float("inf")

    keys = list(b.keys())
    total = 0.0

    for key in keys:
        diff = float(a.get(key, 0.0)) - float(b.get(key, 0.0))
        total += diff * diff

    return (total / max(len(keys), 1)) ** 0.5


# ==================================================
# 현재 얼굴이 어떤 제스처인지 찾기
# ==================================================
def find_gesture(vector, settings):
    candidates = []

    for action_id, data in settings.items():
        if action_id == "neutral":
            continue
        if not isinstance(data, dict) or "vector" not in data:
            continue

        candidates.append({
            "id": action_id,
            "label": data.get("label", action_id),
            "distance": distance(vector, data["vector"])
        })

    candidates.sort(key=lambda item: item["distance"])

    best = candidates[0] if len(candidates) >= 1 else None
    second = candidates[1] if len(candidates) >= 2 else None

    return best, second


# ==================================================
# 실제 마우스 동작 실행
# ==================================================
def execute_mouse_action(action_id):
    if action_id == "left_single":
        pyautogui.click()
        print("왼쪽 클릭 실행")

    elif action_id == "right_single":
        pyautogui.rightClick()
        print("오른쪽 클릭 실행")

    elif action_id == "left_double":
        pyautogui.doubleClick()
        print("왼쪽 더블클릭 실행")

    elif action_id == "scroll_up":
        pyautogui.scroll(5)
        print("스크롤 위 실행")

    elif action_id == "scroll_down":
        pyautogui.scroll(-5)
        print("스크롤 아래 실행")

    else:
        print("알 수 없는 동작:", action_id)


# ==================================================
# 실행
# ==================================================
def main():
    settings = wait_for_gesture_settings()
    neutral_vector = settings["neutral"]["vector"]
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

    print("최종 레이저 + 얼굴 마우스 제어 시작")
    print("종료: q 또는 ESC")
    print(f"레이저 카메라 번호: {LASER_CAMERA_INDEX}")
    print(f"얼굴 카메라 번호: {FACE_CAMERA_INDEX}")

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
            best_candidate, _ = detect_laser(laser_frame)

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
            face_gesture_allowed = laser_detected and stopped_time > STOP_DELAY

            if face_gesture_allowed:
                cv2.putText(
                    laser_frame,
                    "Mouse stopped: Face gesture ON",
                    (30, 75),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )
            else:
                cv2.putText(
                    laser_frame,
                    "Mouse moving/not detected: Face gesture OFF",
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
                mp_image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=face_rgb
                )

                timestamp_ms = int(time.time() * 1000)
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
                    neutral_dist = distance(current_vector, neutral_vector)

                    if neutral_dist < MIN_NEUTRAL_CHANGE:
                        face_text = "No gesture"
                        color = (255, 255, 255)
                        last_label = None
                        stable_count = 0
                    else:
                        best, second = find_gesture(current_vector, settings)

                        if not best:
                            face_text = "No saved gesture"
                            color = (0, 0, 255)
                            last_label = None
                            stable_count = 0
                        else:
                            margin = (second["distance"] if second else float("inf")) - best["distance"]
                            detected = best["distance"] <= TEST_THRESHOLD and margin >= TEST_MARGIN

                            if not detected:
                                face_text = "No gesture"
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
                                    face_text = f"Checking: {best['label']}"
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
        print("PyAutoGUI fail-safe 작동. 마우스가 화면 모서리에 닿아 종료합니다.")

    finally:
        laser_cap.release()
        face_cap.release()
        cv2.destroyAllWindows()
        print("카메라가 꺼졌습니다.")


if __name__ == "__main__":
    start_gesture_save_server()
    main()
