"""프로젝트 공통 설정값."""

from pathlib import Path

import cv2

BASE_DIR = Path(__file__).resolve().parent

# 파일
GESTURE_FILE = BASE_DIR / "gestures.json"
MODEL_FILE = BASE_DIR / "face_landmarker.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
)

# 제스처 저장 서버
SETTINGS_SERVER_HOST = "127.0.0.1"
SETTINGS_SERVER_PORT = 5000

# 카메라
LASER_CAMERA_INDEX = 2
FACE_CAMERA_INDEX = 0
CAMERA_BACKEND = cv2.CAP_DSHOW

# 레이저 인식
R_MIN = 120
RED_DIFF = 18
HSV_S_MIN = 40
HSV_V_MIN = 100

MIN_AREA = 8
MAX_AREA = 1200
MAX_W_H = 90
MIN_FILL_RATIO = 0.03
MIN_LASER_SCORE = 260

LASER_CORE_R_MIN = 175
LASER_CORE_V_MIN = 155
LASER_CORE_RED_DIFF = 30
MIN_CORE_PIXELS = 1

FACE_GESTURE_ALWAYS_ON_FOR_TEST = False

MOVE_THRESHOLD = 8
STOP_DELAY = 0.5
JUMP_THRESHOLD = 140
SMOOTHING_ALPHA = 0.25
MOUSE_DEAD_ZONE = 4

# 얼굴 제스처 인식
GESTURE_DISTANCE_THRESHOLD = 0.115
GESTURE_MARGIN = 0.012
TEST_STABLE_FRAMES = 3
MIN_NEUTRAL_CHANGE = 0.035
MIN_SAVED_GESTURE_STRENGTH = 0.025
MIN_CURRENT_GESTURE_STRENGTH = 0.030

STRONG_GESTURE_STRENGTH = 0.25
STRONG_GESTURE_MARGIN = 0.05
SIGNATURE_MIN_FEATURE_CHANGE = 0.010
SIGNATURE_MAX_FEATURES = 28

ACTION_COOLDOWN = 1.0
SCROLL_AMOUNT = 20
RUNTIME_NEUTRAL_SECONDS = 2.0

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
