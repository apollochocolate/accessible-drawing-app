"""통합 실행에 필요한 설정값만 모아둔 파일."""

import os
import cv2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GESTURE_FILE = os.path.join(BASE_DIR, "gestures.json")
MODEL_FILE = os.path.join(BASE_DIR, "face_landmarker.task")
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/latest/face_landmarker.task"
)

SETTINGS_SERVER_HOST = "127.0.0.1"
SETTINGS_SERVER_PORT = 5000

# Windows 기준. 카메라 번호가 다르면 여기만 수정하면 됩니다.
LASER_CAMERA_INDEX = 0
FACE_CAMERA_INDEX = 1
CAMERA_BACKEND = cv2.CAP_DSHOW
# Mac: CAMERA_BACKEND = cv2.CAP_AVFOUNDATION

# 화면 크기와 영역 경계
WIN_W = 640
WIN_H = 480
MOUSE_ZONE_Y = 250

# 화면 표시 옵션
# False로 두면 카메라 창을 띄우지 않고 터미널 상태 출력만 사용합니다.
SHOW_CAMERA_WINDOWS = True
SHOW_DEBUG_OVERLAY = True
TERMINAL_STATUS_INTERVAL = 0.7


# 레이저 인식 기준값
# v2 안정화: 종이 위의 실제 레이저만 잡도록 기존보다 조금 엄격하게 조정했습니다.
# 레이저가 너무 안 잡히면 R_MIN / HSV_V_MIN / LASER_CORE_* 값을 조금씩 낮추세요.
# 빨간 노이즈를 잡으면 RED_DIFF / LASER_CORE_RED_DIFF / MIN_LASER_SCORE를 올리세요.
R_MIN = 125
RED_DIFF = 20
HSV_S_MIN = 35
HSV_V_MIN = 95
MIN_AREA = 1
MAX_AREA = 900
MAX_W_H = 70
MIN_FILL_RATIO = 0.025
MIN_LASER_SCORE = 270
LASER_CORE_R_MIN = 160
LASER_CORE_V_MIN = 130
LASER_CORE_RED_DIFF = 24
MIN_CORE_PIXELS = 1


# 레이저만 인식하기 위한 배경 차분 필터
# 실행 직후 레이저를 끈 상태의 종이를 1초 정도 저장한 뒤,
# 그 배경과 비교해서 새로 생긴 빨간 점만 레이저 후보로 봅니다.
USE_LASER_BACKGROUND_FILTER = True
LASER_BACKGROUND_CAPTURE_SECONDS = 1.2
LASER_BG_MIN_R_DELTA = 14
LASER_BG_MIN_V_DELTA = 10
LASER_BG_MIN_REDNESS_DELTA = 18
LASER_BG_STRONG_REDNESS_DELTA = 28
LASER_BG_MASK_DILATE = 2

# 레이저 안정화 기준
# 중심부 평균값이 이보다 약하면 빨간 노이즈로 보고 버립니다.
LASER_MIN_LOCAL_RED_DIFF = 10
LASER_MIN_LOCAL_V = 80

# 이전 프레임 레이저 위치 근처 후보를 우선시해서 튐을 줄입니다.
LASER_NEAR_PREVIOUS_BONUS_RADIUS = 85
LASER_FAR_PREVIOUS_PENALTY = 1.8

# 종이 마커를 찾은 뒤에는 종이 영역 안에서만 레이저를 찾습니다.
LASER_DETECT_ONLY_ON_PAPER = True

# 레이저 민감도 보정
# STRICT가 실패하면 종이 안에서 가장 '붉게 튀는 작은 점'을 한 번 더 찾습니다.
LASER_ENABLE_DYNAMIC_FALLBACK = True
LASER_DYNAMIC_PERCENTILE = 99.72
LASER_DYNAMIC_MIN_SCORE = 115.0
LASER_DYNAMIC_MIN_LOCAL_RED_DIFF = 6.0
LASER_DYNAMIC_MIN_LOCAL_V = 55.0
LASER_DYNAMIC_MAX_AREA = 180
LASER_DYNAMIC_MAX_W_H = 34
LASER_DYNAMIC_MIN_SUPPORT_PIXELS = 1

# 종이 위 랜덤 빨간 잡점이 너무 많이 잡힐 때 올리세요.
# 레이저가 너무 안 잡히면 낮추세요.
LASER_DYNAMIC_CONFIRM_MARGIN = 18.0

# 마우스 이동 보정
MOVE_THRESHOLD = 8
STOP_DELAY = 0.5
JUMP_THRESHOLD = 130
JUMP_REACQUIRE_FRAMES = 2
SMOOTHING_ALPHA = 0.18
MOUSE_DEAD_ZONE = 5

# 얼굴 제스처 인식 기준값: v13 방식 유지
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

# 실행 중 중립 얼굴 자동 보정은 기존 얼굴인식 방식으로 되돌리기 위해 꺼둡니다.
AUTO_NEUTRAL_ADAPT = False
NEUTRAL_ADAPT_STABLE_FRAMES = 12      # 이 프레임 수만큼 중립이어야 보정 시작
NEUTRAL_ADAPT_ALPHA = 0.035           # 한 프레임마다 기준점을 섞는 비율. 클수록 빠르지만 오인식 위험 증가
NEUTRAL_ADAPT_MAX_CHANGE = 0.030      # 이 값보다 큰 변화는 제스처일 수 있어 보정하지 않음
NEUTRAL_ADAPT_MIN_INTERVAL = 0.04     # 너무 자주 갱신하지 않기 위한 최소 간격(초)

# True면 레이저 상태와 상관없이 얼굴 제스처를 켭니다.
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

# ==================================================
# 종이 키보드 마커 보정 설정
# ==================================================
# True: 레이저 카메라가 종이 키보드를 보고, 네 모서리 검은 마커를 기준으로 좌표 보정
# False: 기존처럼 카메라 화면 좌표에 고정 키보드 오버레이 사용
USE_PAPER_MARKER_BOARD = True

# A3 세로 종이 디자인 기준 크기
# 파일: A3_세로_종이키보드_정확버전_300dpi.png
# 크기: 3508 x 4961
PAPER_DESIGN_W = 3508
PAPER_DESIGN_H = 4961

# 네 검은 마커 중심 좌표. 순서: 왼쪽 위, 오른쪽 위, 왼쪽 아래, 오른쪽 아래
PAPER_MARKER_CENTERS = [
    (379.0, 477.0),
    (3127.0, 481.0),
    (377.0, 4536.0),
    (3129.0, 4531.0),
]

# A3 세로 디자인 안에서 실제 키보드가 들어있는 영역.
# 이 영역을 기존 keyboard_layout.py의 실제 KEY_MAP 전체 영역으로 변환합니다.
# 이전 값은 y2가 250이라서 종이 하단 빈 공간이 V/B 같은 키로 잘못 매핑될 수 있었습니다.
PAPER_KEYBOARD_BOX = (500.0, 960.0, 3000.0, 2320.0)
VIRTUAL_KEYBOARD_BOX = (80.0, 20.0, 524.0, 282.0)

# A3 세로 디자인 안에서 마우스 영역 기준선과 가로 범위.
PAPER_MOUSE_X1 = 260.0
PAPER_MOUSE_X2 = 3248.0
PAPER_MOUSE_LINE_Y = 2550.0
PAPER_MOUSE_BOTTOM_Y = 4320.0

# 검은 마커 검출 기준.
# 기존보다 작은 마커/어두운 배경에 강하게 조정했습니다.
MARKER_DARK_THRESHOLD = 120
MARKER_MIN_AREA_RATIO = 0.00015
MARKER_MAX_AREA_RATIO = 0.03
MARKER_MIN_SQUARE_RATIO = 0.50
MARKER_MAX_SQUARE_RATIO = 1.60
MARKER_MIN_FILL_RATIO = 0.30


# ==================================================
# Space 키 기준점 인식 설정
# ==================================================
# True: 네 모서리 마커로 종이를 편 뒤, 하단의 긴 Space 키 박스를 찾아
#       키보드 좌표를 한 번 더 보정합니다.
# False: 기존처럼 PAPER_KEYBOARD_BOX 고정 좌표만 사용합니다.
USE_SPACE_ANCHOR = True

# Space를 찾을 종이 디자인 좌표 영역.
# A3 세로 템플릿에서 키보드 하단 줄 주변을 넓게 잡은 값입니다.
# 너무 넓으면 다른 긴 선을 잡을 수 있고, 너무 좁으면 Space를 놓칠 수 있습니다.
SPACE_ANCHOR_SEARCH_BOX = (850.0, 1900.0, 2550.0, 2400.0)

# Space 후보 조건. Space는 하단 줄에서 가로로 가장 긴 키라서 비율로 찾습니다.
SPACE_ANCHOR_DARK_THRESHOLD = 175
SPACE_ANCHOR_MIN_ASPECT = 1.8
SPACE_ANCHOR_MAX_ASPECT = 8.0
SPACE_ANCHOR_MIN_WIDTH_RATIO = 0.35
SPACE_ANCHOR_MAX_WIDTH_RATIO = 2.2
SPACE_ANCHOR_MIN_HEIGHT_RATIO = 0.20
SPACE_ANCHOR_MAX_HEIGHT_RATIO = 2.8
SPACE_ANCHOR_MAX_CENTER_SHIFT = 650.0
SPACE_ANCHOR_ALPHA = 0.35
SPACE_ANCHOR_KEEP_FRAMES = 25
SPACE_ANCHOR_WARP_SCALE = 0.25
SPACE_ANCHOR_DRAW_DEBUG = False

# 터미널 전용 모드: 상태를 계속 출력하지 않고 이벤트만 출력합니다.
TERMINAL_EVENT_LOG_ONLY = True

# 마커 인식 안정화
# 네 모서리 마커를 1~2프레임 놓쳐도 바로 "끊김"으로 처리하지 않고,
# 마지막 정상 인식 후 이 시간(초) 안에는 계속 인식된 것으로 봅니다.
BOARD_MARKER_LOST_GRACE_SECONDS = 1.5
