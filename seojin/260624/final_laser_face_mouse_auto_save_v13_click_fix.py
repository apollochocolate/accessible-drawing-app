"""
final_laser_face_mouse_auto_save_v13_click_fix.py

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
# v3: 빨간 물체를 레이저로 오인하는 문제를 줄이기 위해
# 기존보다 훨씬 엄격하게 잡았습니다.
# 레이저가 너무 안 잡히면 R_MIN, RED_DIFF, HSV_V_MIN을 조금씩 낮추세요.
# v5: v4가 너무 빡세서 레이저를 못 잡는 문제를 줄이기 위해 완화했습니다.
# 빨간 점을 너무 많이 잡으면 R_MIN/RED_DIFF/HSV_V_MIN을 올리세요.
# 레이저를 못 잡으면 R_MIN/RED_DIFF/HSV_V_MIN을 내리세요.
R_MIN = 120
RED_DIFF = 18
HSV_S_MIN = 40
HSV_V_MIN = 100

# v8: 빨간 노이즈를 줄이고, 실제 레이저 점만 잡기 위한 기본값
MIN_AREA = 8
MAX_AREA = 1200
MAX_W_H = 90
MIN_CIRCULARITY = 0.04
MIN_FILL_RATIO = 0.03
MIN_LASER_SCORE = 260

# v10: 레이저가 없을 때 아무 빨간 노이즈나 잡지 않도록,
# 후보 안에 밝은 "핵심 점"이 있을 때만 레이저로 인정합니다.
LASER_CORE_R_MIN = 175
LASER_CORE_V_MIN = 155
LASER_CORE_RED_DIFF = 30
MIN_CORE_PIXELS = 1

# 디버깅용. True면 레이저가 안 잡혀도 얼굴 제스처를 항상 켜서 테스트합니다.
# 얼굴 제스처가 잘 되는 걸 확인한 뒤 최종 시연 때는 False로 바꾸세요.
FACE_GESTURE_ALWAYS_ON_FOR_TEST = False

# 문제 확인용. True로 바꾸면 레이저 마스크 창이 하나 더 뜹니다.
SHOW_LASER_MASK = False

x_history = deque(maxlen=5)
y_history = deque(maxlen=5)

MOVE_THRESHOLD = 8
STOP_DELAY = 0.5

JUMP_THRESHOLD = 140
SMOOTHING_ALPHA = 0.25
MOUSE_DEAD_ZONE = 4


# ==================================================
# 얼굴 제스처 인식 기준값
# HTML 설정 파일과 같은 기준으로 맞춤
# ==================================================
# v3: HTML에서 저장한 delta 값을 사용해서 인식합니다.
# 기존의 절대 벡터 비교보다 조명/얼굴 위치 변화에 조금 더 강합니다.
# v5: 처음 테스트가 너무 안 잡히는 문제를 줄이기 위해 기준을 완화했습니다.
# v9: 중립 얼굴을 클릭으로 오인식하지 않도록 기준을 강화했습니다.
# 중립인데 클릭으로 뜨면 MIN_NEUTRAL_CHANGE를 더 올리세요.
# 실제 제스처가 너무 안 잡히면 GESTURE_DISTANCE_THRESHOLD를 조금 올리세요.
# v12: 특정 동작을 하드코딩하지 않고, HTML에서 저장한 얼굴 변화 전체를 비교합니다.
# 고개 돌림/yaw, 고개 기울임/roll, 고개 숙임/pitch, 눈 감김, 입 벌림 등을 모두 특징으로 사용합니다.
GESTURE_DISTANCE_THRESHOLD = 0.115
GESTURE_MARGIN = 0.012
TEST_STABLE_FRAMES = 3
MIN_NEUTRAL_CHANGE = 0.035
MIN_SAVED_GESTURE_STRENGTH = 0.025
MIN_CURRENT_GESTURE_STRENGTH = 0.030

# v13: 저장 제스처와 거리는 조금 멀어도, 현재 얼굴 변화가 충분히 크고
# 1등 후보가 2등 후보보다 확실히 앞서면 실행하도록 보조 판정 추가.
# 화면에 Closest만 뜨고 클릭이 안 되는 문제를 줄입니다.
STRONG_GESTURE_STRENGTH = 0.25
STRONG_GESTURE_MARGIN = 0.05
SIGNATURE_MIN_FEATURE_CHANGE = 0.010
SIGNATURE_MAX_FEATURES = 28
ACTION_COOLDOWN = 1.0

# v12에서는 왼쪽/오른쪽 클릭도 저장된 제스처 벡터로 인식합니다.
# 사용자가 고개를 돌리든, 기울이든, 숙이든, 눈을 감든 저장한 방식 그대로 비교합니다.
HEAD_TILT_CLICK_MODE = False
HEAD_TILT_THRESHOLD = 0.055
HEAD_TILT_STABLE_FRAMES = 4
HEAD_TILT_LEFT_RIGHT_REVERSED = False

# 실행 시작 직전에 Python 얼굴 카메라 기준으로 중립 얼굴을 다시 잡습니다.
# HTML에서 저장한 중립과 Python 실행 중 중립이 조금 달라도 오인식을 줄이기 위함입니다.
RUNTIME_NEUTRAL_SECONDS = 2.0


# ==================================================
# PyAutoGUI 설정
# ==================================================
screen_w, screen_h = pyautogui.size()
pyautogui.FAILSAFE = False  # 화면 모서리로 가도 프로그램이 꺼지지 않게 설정
pyautogui.PAUSE = 0


# ==================================================
# 제스처 설정 불러오기
# ==================================================

# 반드시 저장되어 있어야 하는 제스처 목록
# neutral은 기준 얼굴이고, 나머지는 실제 클릭/스크롤 동작입니다.
REQUIRED_GESTURE_IDS = [
    "neutral",
    "left_single",
    "right_single",
    "left_double",
    "scroll_up",
    "scroll_down",
]

REQUIRED_GESTURE_LABELS = {
    "neutral": "기본 중립 얼굴",
    "left_single": "마우스 왼쪽 싱글클릭",
    "right_single": "마우스 오른쪽 싱글클릭",
    "left_double": "마우스 왼쪽 더블클릭",
    "scroll_up": "스크롤 위",
    "scroll_down": "스크롤 아래",
}


ACTION_DISPLAY_NAMES = {
    "left_single": "left click",
    "right_single": "right click",
    "left_double": "double click",
    "scroll_up": "scroll up",
    "scroll_down": "scroll down",
}

def load_gesture_settings():
    if not os.path.exists(GESTURE_FILE):
        raise FileNotFoundError(
            f"gestures.json 파일이 없습니다. 필요한 위치: {GESTURE_FILE}"
        )

    with open(GESTURE_FILE, "r", encoding="utf-8") as f:
        settings = json.load(f)

    missing = []
    for gesture_id in REQUIRED_GESTURE_IDS:
        data = settings.get(gesture_id)
        if not isinstance(data, dict) or "vector" not in data:
            missing.append(REQUIRED_GESTURE_LABELS.get(gesture_id, gesture_id))

    if missing:
        raise ValueError("아직 저장되지 않은 제스처: " + ", ".join(missing))

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
def detect_laser(frame, prefer_point=None):
    """
    v10 레이저 검출 방식
    - 레이저가 없으면 None을 반환해서 마우스를 움직이지 않습니다.
    - 빨간 배경/노이즈가 아니라, 밝은 빨간 핵심 점(core)이 있는 후보만 인정합니다.
    - 마스크 디버그 창은 띄우지 않습니다.
    """
    b, g, r = cv2.split(frame)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, s_ch, v = cv2.split(hsv)

    r_i = r.astype(np.int16)
    g_i = g.astype(np.int16)
    b_i = b.astype(np.int16)
    h_i = h.astype(np.int16)
    s_i = s_ch.astype(np.int16)
    v_i = v.astype(np.int16)

    red_over_green = r_i - g_i
    red_over_blue = r_i - b_i

    # 1차 후보: 빨간/분홍 계열이며 어느 정도 밝은 픽셀
    hue_red_or_pink = (h_i <= 18) | (h_i >= 155)
    color_candidate = (
        hue_red_or_pink &
        (s_i >= HSV_S_MIN) &
        (v_i >= HSV_V_MIN) &
        (r_i >= R_MIN) &
        (red_over_green >= RED_DIFF) &
        (red_over_blue >= -20)
    )

    # 핵심 후보: 실제 레이저 점처럼 밝고 빨간 중심부
    core_candidate = (
        (r_i >= LASER_CORE_R_MIN) &
        (v_i >= LASER_CORE_V_MIN) &
        (red_over_green >= LASER_CORE_RED_DIFF) &
        (hue_red_or_pink | (s_i >= 25))
    )

    laser_pixel = color_candidate | core_candidate
    mask = laser_pixel.astype(np.uint8) * 255
    mask = cv2.medianBlur(mask, 3)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    score_img = (
        v_i.astype(np.float32) * 1.4 +
        r_i.astype(np.float32) * 1.0 +
        s_i.astype(np.float32) * 0.4 +
        np.maximum(red_over_green, 0).astype(np.float32) * 3.5
    )

    candidates = []

    for contour in contours:
        area = cv2.contourArea(contour)
        if not (MIN_AREA <= area <= MAX_AREA):
            continue

        x, y, w, h_box = cv2.boundingRect(contour)
        if w <= 0 or h_box <= 0:
            continue
        if w > MAX_W_H or h_box > MAX_W_H:
            continue

        ratio = w / h_box
        if ratio < 0.2 or ratio > 5.0:
            continue

        rect_area = max(w * h_box, 1)
        fill_ratio = area / rect_area
        if fill_ratio < MIN_FILL_RATIO:
            continue

        # 이 후보 안에 진짜 밝은 core가 없으면 레이저가 아니라고 봅니다.
        core_roi = core_candidate[y:y + h_box, x:x + w]
        core_pixels = int(np.count_nonzero(core_roi))
        if core_pixels < MIN_CORE_PIXELS:
            continue

        component_mask = np.zeros(mask.shape, dtype=np.uint8)
        cv2.drawContours(component_mask, [contour], -1, 255, -1)
        masked_score = np.where(component_mask > 0, score_img, -1)
        _, max_score, _, max_loc = cv2.minMaxLoc(masked_score.astype(np.float32))
        cx, cy = max_loc

        if max_score < MIN_LASER_SCORE:
            continue

        x1 = max(cx - 4, 0)
        x2 = min(cx + 5, frame.shape[1])
        y1 = max(cy - 4, 0)
        y2 = min(cy + 5, frame.shape[0])

        local_r = float(np.mean(r[y1:y2, x1:x2]))
        local_g = float(np.mean(g[y1:y2, x1:x2]))
        local_s = float(np.mean(s_ch[y1:y2, x1:x2]))
        local_v = float(np.mean(v[y1:y2, x1:x2]))
        local_red_green = local_r - local_g

        score = float(max_score) + core_pixels * 15 + local_v * 0.8 + max(local_red_green, 0) * 2.5

        # 이전 위치와 너무 멀리 튄 후보는 조금 감점만 합니다.
        # 단, 레이저를 새 위치에 다시 비출 수도 있으니 완전히 버리지는 않습니다.
        if prefer_point and prefer_point[0] is not None and prefer_point[1] is not None:
            px, py = prefer_point
            dist = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
            if dist < 120:
                score += 100 - dist * 0.4
            else:
                score -= min(dist * 0.25, 140)

        candidates.append({
            "x": int(cx),
            "y": int(cy),
            "area": float(area),
            "score": float(score),
            "red_strength": float(local_red_green),
            "v": float(local_v),
            "s": float(local_s),
            "w": int(w),
            "h": int(h_box),
            "core": int(core_pixels),
        })

    if not candidates:
        return None, mask

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates[0], mask

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
    """
    얼굴 인식 결과를 숫자 벡터로 바꿉니다.
    v12 핵심:
    - 표정 blendshape 전체
    - 고개 좌우 회전 yaw
    - 고개 좌우 기울임 roll
    - 고개 위/아래 pitch
    - 입 벌림/입 너비
    - 양쪽 눈 감김 정도
    - 눈썹 움직임
    을 모두 저장/비교합니다.
    """
    vector = {}

    # 1) MediaPipe blendshape 점수: 눈 감김, 입 벌림, 미소, 찡그림 등
    if result.face_blendshapes:
        for category in result.face_blendshapes[0]:
            try:
                vector[category.category_name] = float(category.score)
            except Exception:
                pass

    landmarks = result.face_landmarks[0] if result.face_landmarks else None

    if landmarks:
        try:
            # 주요 랜드마크
            nose = landmarks[1]
            forehead = landmarks[10]
            chin = landmarks[152]
            left_eye_outer = landmarks[33]
            right_eye_outer = landmarks[263]
            left_cheek = landmarks[234]
            right_cheek = landmarks[454]

            face_w = max(abs(right_cheek.x - left_cheek.x), 0.001)
            face_h = max(abs(chin.y - forehead.y), 0.001)
            eye_y = (left_eye_outer.y + right_eye_outer.y) / 2
            face_center_x = (left_cheek.x + right_cheek.x) / 2

            # 고개 숙임/듦, 좌우 돌림, 좌우 기울임
            vector["__head_pitch_nose"] = float((nose.y - eye_y) / face_h)
            vector["__head_pitch_chin"] = float((chin.y - eye_y) / face_h)
            vector["__head_yaw"] = float((nose.x - face_center_x) / face_w)
            vector["__head_roll"] = float((right_eye_outer.y - left_eye_outer.y) / face_w)
            vector["__head_z"] = float((nose.z or 0) / face_h)

            # 입 벌림/입 너비. 13/14는 위아래 입술, 61/291은 입꼬리 쪽.
            upper_lip = landmarks[13]
            lower_lip = landmarks[14]
            mouth_left = landmarks[61]
            mouth_right = landmarks[291]
            vector["__mouth_open_lm"] = float(abs(lower_lip.y - upper_lip.y) / face_h)
            vector["__mouth_width_lm"] = float(abs(mouth_right.x - mouth_left.x) / face_w)

            # 눈 열림 정도. 값이 작아지면 눈을 감은 것.
            l_top = landmarks[159]
            l_bottom = landmarks[145]
            r_top = landmarks[386]
            r_bottom = landmarks[374]
            vector["__left_eye_open_lm"] = float(abs(l_bottom.y - l_top.y) / face_h)
            vector["__right_eye_open_lm"] = float(abs(r_bottom.y - r_top.y) / face_h)

            # 눈썹 움직임. 값이 커지면 눈썹/이마 쪽 움직임이 커진 것.
            left_brow = landmarks[105]
            right_brow = landmarks[334]
            vector["__left_brow_raise_lm"] = float(abs(left_eye_outer.y - left_brow.y) / face_h)
            vector["__right_brow_raise_lm"] = float(abs(right_eye_outer.y - right_brow.y) / face_h)
        except Exception:
            pass

    # pose matrix는 JS/Python 간 차이가 커서 기본 매칭에서는 사용하지 않습니다.
    # 그래도 저장해두면 나중에 디버깅할 수 있어서 낮은 가중치 후보로 남겨둡니다.
    if result.facial_transformation_matrixes:
        try:
            matrix = result.facial_transformation_matrixes[0]
            data = getattr(matrix, "data", None)
            if data is None:
                flat_data = np.asarray(matrix, dtype=np.float32).reshape(-1)
            else:
                flat_data = np.asarray(data, dtype=np.float32).reshape(-1)
            for i, value in enumerate(flat_data):
                vector[f"__pose_{i}"] = float(value) * 0.05
        except Exception:
            pass

    return vector if vector else None


# ==================================================
# 벡터 거리 계산
# ==================================================

def feature_weight(key):
    """특징별 가중치. 고개/눈/입 움직임은 blendshape보다 조금 더 강하게 봅니다."""
    if key.startswith("__pose_"):
        return 0.0
    if key == "__head_z":
        return 0.0
    if key.startswith("__head_"):
        return 2.4
    if key.startswith("__eye_"):
        return 3.0
    if key.startswith("__mouth_"):
        return 2.8
    if key.startswith("__left_brow") or key.startswith("__right_brow"):
        return 2.0
    # blendshape 중에서도 눈/입/턱 계열은 중요하게 봄
    lower = key.lower()
    if "eye" in lower or "blink" in lower:
        return 2.3
    if "mouth" in lower or "jaw" in lower or "lip" in lower:
        return 2.2
    if "brow" in lower:
        return 1.8
    return 1.0


def normalize_match_vector(vector):
    if not vector:
        return {}

    result = {}
    for key, value in vector.items():
        w = feature_weight(key)
        if w <= 0:
            continue
        try:
            v = float(value)
        except Exception:
            continue
        result[key] = v * w
    return result


def make_signature(target_delta):
    """
    저장된 제스처에서 실제로 많이 변한 특징만 뽑습니다.
    예: 고개를 왼쪽으로 내리는 제스처면 head_roll/head_pitch가 주요 특징이 됨.
    예: 입 벌리기면 jawOpen/mouth_open이 주요 특징이 됨.
    """
    target = normalize_match_vector(target_delta)
    items = [(k, v) for k, v in target.items() if abs(v) >= SIGNATURE_MIN_FEATURE_CHANGE]
    items.sort(key=lambda kv: abs(kv[1]), reverse=True)
    items = items[:SIGNATURE_MAX_FEATURES]
    return dict(items)


def weighted_signature_distance(current_delta, signature):
    if not current_delta or not signature:
        return float("inf")

    current = normalize_match_vector(current_delta)
    total = 0.0
    weight_sum = 0.0

    for key, target_value in signature.items():
        current_value = current.get(key, 0.0)
        # 많이 변한 특징일수록 더 중요하게 비교
        w = max(abs(target_value), 0.012)
        diff = current_value - target_value

        # 방향이 완전히 반대면 강한 패널티. 왼쪽/오른쪽, 위/아래 구분에 중요함.
        if abs(target_value) >= SIGNATURE_MIN_FEATURE_CHANGE and current_value * target_value < 0:
            diff *= 1.8

        total += w * diff * diff
        weight_sum += w

    return (total / max(weight_sum, 1e-9)) ** 0.5


def vector_strength_on_signature(current_delta, signature):
    current = normalize_match_vector(current_delta)
    if not current or not signature:
        return 0.0
    values = [current.get(k, 0.0) for k in signature.keys()]
    if not values:
        return 0.0
    return (sum(v * v for v in values) / len(values)) ** 0.5


def average_vectors(vectors):
    if not vectors:
        return None

    avg = {}
    count = {}
    for vector in vectors:
        for key, value in vector.items():
            try:
                value = float(value)
            except Exception:
                continue
            avg[key] = avg.get(key, 0.0) + value
            count[key] = count.get(key, 0) + 1

    for key in list(avg.keys()):
        avg[key] /= max(count.get(key, 1), 1)

    return avg

def distance(a, b):
    if not a or not b:
        return float("inf")

    keys = list(b.keys())
    total = 0.0

    for key in keys:
        diff = float(a.get(key, 0.0)) - float(b.get(key, 0.0))
        total += diff * diff

    return (total / max(len(keys), 1)) ** 0.5


def vector_delta(vector, neutral):
    if not vector or not neutral:
        return None

    result = {}
    keys = set(vector.keys()) | set(neutral.keys())

    for key in keys:
        result[key] = float(vector.get(key, 0.0)) - float(neutral.get(key, 0.0))

    return result


def vector_magnitude(vector):
    if not vector:
        return 0.0
    values = [float(v) for v in vector.values()]
    if not values:
        return 0.0
    return (sum(v * v for v in values) / len(values)) ** 0.5


# ==================================================
# 현재 얼굴이 어떤 제스처인지 찾기
# ==================================================
def find_gesture(current_delta, settings):
    """
    v12: 모든 동작을 저장된 얼굴 변화 패턴으로 비교합니다.
    특정 동작을 고개 기울임/돌림으로 하드코딩하지 않습니다.
    """
    candidates = []
    neutral_saved = settings.get("neutral", {}).get("vector")

    for action_id, data in settings.items():
        if action_id == "neutral":
            continue
        if not isinstance(data, dict):
            continue

        target_raw = data.get("delta")
        if not target_raw and data.get("vector") and neutral_saved:
            target_raw = vector_delta(data.get("vector"), neutral_saved)
        if not target_raw:
            continue

        signature = make_signature(target_raw)
        if not signature:
            continue

        target_strength = vector_magnitude(signature)
        if target_strength < MIN_SAVED_GESTURE_STRENGTH:
            continue

        dist = weighted_signature_distance(current_delta, signature)
        current_strength = vector_strength_on_signature(current_delta, signature)

        candidates.append({
            "id": action_id,
            "label": ACTION_DISPLAY_NAMES.get(action_id, action_id),
            "distance": dist,
            "strength": target_strength,
            "current_strength": current_strength,
            "signature_keys": list(signature.keys()),
        })

    candidates.sort(key=lambda item: item["distance"])
    best = candidates[0] if len(candidates) >= 1 else None
    second = candidates[1] if len(candidates) >= 2 else None
    return best, second


# ==================================================
# 고개 좌/우 기울임으로 클릭 후보 찾기
# ==================================================
def detect_head_tilt_click(current_vector, neutral_vector):
    if not HEAD_TILT_CLICK_MODE:
        return None, 0.0

    current_roll = current_vector.get("__head_roll") if current_vector else None
    neutral_roll = neutral_vector.get("__head_roll") if neutral_vector else 0.0

    if current_roll is None:
        return None, 0.0

    roll_delta = float(current_roll) - float(neutral_roll or 0.0)

    if HEAD_TILT_LEFT_RIGHT_REVERSED:
        roll_delta = -roll_delta

    # 카메라 좌표계에서는 부호가 환경마다 반대로 느껴질 수 있습니다.
    # 왼쪽/오른쪽이 반대로 실행되면 HEAD_TILT_LEFT_RIGHT_REVERSED=True로 바꾸세요.
    if roll_delta <= -HEAD_TILT_THRESHOLD:
        return "left_single", roll_delta

    if roll_delta >= HEAD_TILT_THRESHOLD:
        return "right_single", roll_delta

    return None, roll_delta

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
# Python 실행 시점의 중립 얼굴 캘리브레이션
# ==================================================
def capture_runtime_neutral(face_cap, face_landmarker):
    print("Python 얼굴 카메라 기준 중립 얼굴을 다시 캘리브레이션합니다.")
    print("2초 동안 가만히 정면을 봐주세요.")

    samples = []
    last_ts = 0
    start = time.time()

    while time.time() - start < RUNTIME_NEUTRAL_SECONDS:
        ret, frame = face_cap.read()
        if not ret:
            continue

        remain = max(0.0, RUNTIME_NEUTRAL_SECONDS - (time.time() - start))
        cv2.putText(
            frame,
            f"Neutral calibration {remain:.1f}s",
            (30, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 255),
            2
        )
        cv2.imshow("Face Gesture Control", frame)
        cv2.waitKey(1)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb = np.ascontiguousarray(rgb)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        ts = int(time.time() * 1000)
        if ts <= last_ts:
            ts = last_ts + 1
        last_ts = ts

        result = face_landmarker.detect_for_video(mp_image, ts)
        vector = make_face_vector(result)
        if vector:
            samples.append(vector)

    neutral = average_vectors(samples)
    if not neutral:
        print("실행 중립 얼굴 캘리브레이션 실패. HTML 중립 얼굴을 사용합니다.")
        return None, last_ts

    print(f"실행 중립 얼굴 캘리브레이션 완료: {len(samples)} samples")
    return neutral, last_ts

# ==================================================
# 실행
# ==================================================
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
            best_candidate, mask = detect_laser(
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
