"""
config_combined.py
레이저 키보드/마우스 + 얼굴 제스처 실행에 필요한 설정값만 모아둔 파일.
카메라 번호나 인식 기준값은 주로 여기서 수정하면 됩니다.
"""

import os
import cv2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GESTURE_FILE = os.path.join(BASE_DIR, "gestures.json")
MODEL_FILE = os.path.join(BASE_DIR, "face_landmarker.task")
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"

SETTINGS_SERVER_HOST = "127.0.0.1"
SETTINGS_SERVER_PORT = 5000

# 카메라 번호: 환경에 맞게 바꾸세요.
LASER_CAMERA_INDEX = 2
FACE_CAMERA_INDEX = 0
CAMERA_BACKEND = cv2.CAP_DSHOW
# Mac이면 위 줄 대신 아래 줄을 사용하세요.
# CAMERA_BACKEND = cv2.CAP_AVFOUNDATION

# 키보드/마우스 판 크기
WIN_W = 640
WIN_H = 480
MOUSE_ZONE_Y = 250

# 레이저 인식 기준값
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

# 레이저/마우스 보정값
MOVE_THRESHOLD = 8
STOP_DELAY = 0.5
JUMP_THRESHOLD = 140
SMOOTHING_ALPHA = 0.25
MOUSE_DEAD_ZONE = 4

# 얼굴 제스처 인식 기준값
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
RUNTIME_NEUTRAL_SECONDS = 2.0

# True면 레이저 상태와 상관없이 얼굴 제스처를 켜서 테스트합니다.
FACE_GESTURE_ALWAYS_ON_FOR_TEST = False

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
