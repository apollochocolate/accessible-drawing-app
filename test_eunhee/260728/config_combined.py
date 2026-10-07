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
LASER_CAMERA_INDEX = 1
FACE_CAMERA_INDEX = 0
CAMERA_BACKEND = cv2.CAP_DSHOW
# Mac: CAMERA_BACKEND = cv2.CAP_AVFOUNDATION

# 레이저 카메라의 종이 검출 전용 캡처 해상도.
# 레이저 검출/화면 표시는 그대로 WIN_W x WIN_H(640x480)를 쓰고,
# 종이 외곽선(또는 마커) 검출만 이 해상도의 원본 프레임에서 수행한 뒤
# 좌표를 640x480 기준으로 환산합니다. 웹캠이 이 해상도를 지원하지 않으면
# 드라이버가 조용히 다른 값으로 낮출 수 있으니, 실행 시 터미널에 찍히는
# "실제 적용된 해상도" 로그를 보고 필요하면 낮추세요.
LASER_CAPTURE_W = 1280
LASER_CAPTURE_H = 720

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

# 좌표 보정 방식 선택 (USE_PAPER_MARKER_BOARD = True 일 때만 의미 있음)
#   "marker" : 기존 방식. 종이 네 모서리 검은 정사각형 마커 4개를 인식 (paper_board_mapper)
#   "edge"   : 새 방식. 종이 사각형 외곽선을 자동 인식, 마커 인쇄 불필요 (paper_edge_mapper)
# 기존 동작을 유지하려면 "marker" 로 두세요.
PAPER_MAPPER_MODE = "edge"

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
# 용지 테두리 자동 인식 설정 (PAPER_MAPPER_MODE = "edge" 일 때 사용)
# ==================================================
# 종이에 마커를 인쇄하지 않고, 종이 사각형 외곽선을 직접 찾아 좌표를 보정합니다.
# True  : Canny 에지 기반. 배경과 종이 밝기 대비가 약해도 경계선이 살아있으면 잘 잡힘.
# False : Otsu 이진화 기반. "어두운 책상 위 밝은 종이" 처럼 대비가 뚜렷하면 더 안정적.
PAPER_EDGE_USE_CANNY = True
PAPER_EDGE_CANNY_LOW = 50
PAPER_EDGE_CANNY_HIGH = 150

# 종이가 화면에서 차지해야 하는 최소/최대 넓이 비율.
# 너무 작은 사각형(글자칸)이나 화면 전체(배경)를 종이로 오인하지 않게 걸러냅니다.
PAPER_EDGE_MIN_AREA_RATIO = 0.08
PAPER_EDGE_MAX_AREA_RATIO = 0.98

# approxPolyDP 근사 정밀도(둘레 대비 비율). 값이 크면 더 거칠게 4각형으로 단순화.
PAPER_EDGE_APPROX_EPS_RATIO = 0.02

# A3 세로 종이의 목표 종횡비(긴 변/짧은 변 = 4961/3508 ≒ 1.414).
# 이 비율에서 크게 벗어난 사각형(모니터/책상 모서리 등)을 걸러냅니다.
# 0 으로 두면 종횡비 검사를 끕니다.
PAPER_EDGE_ASPECT_TARGET = 4961.0 / 3508.0
PAPER_EDGE_ASPECT_TOLERANCE = 0.35

# 종이 물리적 꼭짓점을 디자인 좌표의 어느 지점으로 매핑할지의 여백(px).
# 0 이면 종이 외곽선을 디자인 (0,0)~(W,H) 모서리에 그대로 맞춥니다.
PAPER_EDGE_MARGIN = 0.0

# 프레임 간 꼭짓점 떨림을 줄이는 EMA 계수(0~1). 1 이면 스무딩 없음.
# 값이 작을수록 부드럽지만 종이를 움직였을 때 따라오는 속도가 느려집니다.
PAPER_EDGE_SMOOTH_ALPHA = 0.5

# 디버그 화면에 찾은 종이 외곽선(노란 사각형)을 그릴지 여부.
PAPER_EDGE_DRAW_DEBUG = True

# 종이를 못 찾거나(이상치로 거부된 경우 포함) 이 프레임 수 이내면
# 오버레이/상태를 이전 정상값으로 유지합니다. 이 수를 넘기면 진짜로
# "못 찾음" 상태로 전환합니다. 손이 모서리를 잠깐 스치는 정도의 순간적인
# 인식 실패에도 노란 사각형이 매 프레임 깜빡이는 것을 막기 위한 값입니다.
PAPER_EDGE_HOLD_FRAMES = 10

# 프레임 간 종이 사각형 중심 이동 허용 최대치(px, 640x480 기준).
# 이보다 크게 튀면 노이즈로 보고 그 프레임은 버립니다(EMA에 섞지 않음).
# 너무 낮으면 종이를 빠르게 움직였을 때 정상 이동까지 거부될 수 있고,
# 너무 높으면 노이즈성 오검출을 그대로 받아들이게 됩니다.
PAPER_EDGE_MAX_CENTER_SHIFT = 150.0


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
