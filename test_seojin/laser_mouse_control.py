import cv2
import numpy as np
import pyautogui
import time
from collections import deque


# =========================
# 기본 설정
# =========================
CAMERA_INDEX = 0  # 내장캠은 보통 0, 안 되면 1, 2로 변경

# 레이저 인식 기준값
R_MIN = 120        # 빨간 채널 최소 밝기
RED_DIFF = 25      # R이 G/B보다 얼마나 더 강해야 하는지

# 레이저 점 크기 조건
MIN_AREA = 1       # 너무 작은 노이즈 제외
MAX_AREA = 300     # 너무 큰 빨간 덩어리 제외
MAX_W_H = 50       # 가로/세로가 너무 큰 후보 제외

# 좌표 흔들림 보정
x_history = deque(maxlen=5)
y_history = deque(maxlen=5)

# 마우스 이동/정지 판단
MOVE_THRESHOLD = 8      # 이 픽셀 이상 레이저가 움직이면 이동 중
STOP_DELAY = 0.5        # 이 시간 이상 움직임이 없으면 멈춤

# 마우스 흔들림 보정
JUMP_THRESHOLD = 90       # 레이저 좌표가 갑자기 이 이상 튀면 무시
SMOOTHING_ALPHA = 0.25    # 작을수록 부드럽고 느림, 클수록 빠르고 흔들림
MOUSE_DEAD_ZONE = 4       # 이 픽셀 이하 마우스 흔들림은 무시

# 이전 좌표 저장
last_laser_x = None
last_laser_y = None
last_valid_laser_x = None
last_valid_laser_y = None

# 부드럽게 보정된 마우스 좌표
smoothed_screen_x = None
smoothed_screen_y = None

# 마지막으로 레이저가 움직인 시간
last_move_time = time.time()

# 실제 모니터 화면 크기
screen_w, screen_h = pyautogui.size()

# PyAutoGUI 설정
pyautogui.FAILSAFE = True   # 마우스가 화면 모서리로 가면 긴급 정지
pyautogui.PAUSE = 0


# =========================
# 레이저 좌표 찾기 함수
# =========================
def detect_laser(frame):
    # BGR 채널 분리
    b, g, r = cv2.split(frame)

    # overflow 방지를 위해 int16으로 변환
    r_i = r.astype(np.int16)
    g_i = g.astype(np.int16)
    b_i = b.astype(np.int16)

    # BGR 기준 빨간색 조건
    red_by_bgr = (
        (r_i > R_MIN) &
        (r_i > g_i + RED_DIFF) &
        (r_i > b_i + RED_DIFF)
    )

    # HSV 기준 빨간색 조건 추가
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

    # 둘 중 하나라도 만족하면 레이저 후보
    laser_pixel = red_by_bgr | red_by_hsv

    # True/False 값을 흰색/검은색 마스크로 변환
    mask = laser_pixel.astype(np.uint8) * 255

    # 작은 노이즈 제거
    mask = cv2.medianBlur(mask, 3)

    # 흰색 덩어리 찾기
    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    best_candidate = None
    best_score = -1

    for contour in contours:
        area = cv2.contourArea(contour)

        # 너무 작거나 너무 큰 덩어리 제외
        if not (MIN_AREA < area < MAX_AREA):
            continue

        x, y, w, h_box = cv2.boundingRect(contour)

        # 가로/세로가 너무 큰 후보 제외
        if w > MAX_W_H or h_box > MAX_W_H:
            continue

        # 너무 길쭉한 후보 제외
        ratio = w / h_box if h_box != 0 else 0

        if ratio < 0.3 or ratio > 3.0:
            continue

        # 후보 중심 좌표 계산
        M = cv2.moments(contour)

        if M["m00"] == 0:
            continue

        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])

        # 더 빨갛고 적당히 큰 후보 우선 선택
        score = int(r[cy, cx]) + area

        if score > best_score:
            best_score = score
            best_candidate = {
                "x": cx,
                "y": cy,
                "area": area
            }

    return best_candidate, mask


# =========================
# 카메라 좌표 → 실제 화면 좌표 변환
# =========================
def camera_to_screen(laser_x, laser_y, frame_w, frame_h, screen_w, screen_h):
    rel_x = laser_x / frame_w
    rel_y = laser_y / frame_h

    # 0~1 범위로 제한
    rel_x = max(0, min(1, rel_x))
    rel_y = max(0, min(1, rel_y))

    # 실제 모니터 좌표로 변환
    screen_x = int(rel_x * screen_w)
    screen_y = int(rel_y * screen_h)

    # 화면 밖으로 나가지 않게 제한
    screen_x = max(0, min(screen_w - 1, screen_x))
    screen_y = max(0, min(screen_h - 1, screen_y))

    return screen_x, screen_y


# =========================
# 마우스가 멈췄을 때 얼굴인식 연결할 자리
# =========================
def face_recognition_ready():
    """
    나중에 여기에 얼굴 제스처 인식 결과를 연결하면 됨.

    예:
    pyautogui.click()
    pyautogui.rightClick()
    pyautogui.doubleClick()
    pyautogui.scroll(5)
    pyautogui.scroll(-5)
    """
    pass


# =========================
# 카메라 열기 - 윈도우 VS Code용
# =========================
cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)

if not cap.isOpened():
    print("카메라를 열 수 없습니다.")
    print("CAMERA_INDEX를 0, 1, 2로 바꿔보세요.")
    exit()


print("레이저 마우스 제어 시작")
print("카메라가 켜지면 바로 전체 화면 기준으로 인식합니다.")
print("종료하려면 q 또는 ESC를 누르세요.")
print("마우스가 움직이는 동안: 얼굴 제스처 OFF")
print("마우스가 멈추면: 얼굴 제스처 ON")


try:
    while True:
        ret, frame = cap.read()

        if not ret:
            print("프레임을 읽을 수 없습니다.")
            continue

        # 필요하면 좌우 반전
        # 움직임이 반대로 느껴지면 아래 줄 주석 해제
        # frame = cv2.flip(frame, 1)

        frame_h, frame_w = frame.shape[:2]

        best_candidate, mask = detect_laser(frame)

        laser_detected = False
        jump_ignored = False

        if best_candidate is not None:
            laser_detected = True

            raw_x = best_candidate["x"]
            raw_y = best_candidate["y"]

            # 현재 좌표 저장
            x_history.append(raw_x)
            y_history.append(raw_y)

            # median으로 좌표 흔들림 보정
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

            # 큰 튐이 아닐 때만 마우스 이동 처리
            if not jump_ignored:
                # 카메라 좌표를 실제 화면 좌표로 변환
                screen_x, screen_y = camera_to_screen(
                    laser_x,
                    laser_y,
                    frame_w,
                    frame_h,
                    screen_w,
                    screen_h
                )

                # =========================
                # 레이저 이동량 계산
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
                # 화면 좌표 부드럽게 보정
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

                # =========================
                # 너무 작은 마우스 흔들림은 무시
                # =========================
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
                        break

                # 화면 표시
                cv2.putText(
                    frame,
                    f"Mouse ({smoothed_screen_x}, {smoothed_screen_y})",
                    (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 255),
                    2
                )

            # 레이저 위치 표시
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
            # 레이저가 안 잡히면 보정값 초기화
            x_history.clear()
            y_history.clear()

            last_laser_x = None
            last_laser_y = None
            last_valid_laser_x = None
            last_valid_laser_y = None

            smoothed_screen_x = None
            smoothed_screen_y = None

            cv2.putText(
                frame,
                "Laser not detected",
                (30, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )

        # =========================
        # 마우스 이동 중/정지 상태 판단
        # =========================
        stopped_time = time.time() - last_move_time

        if laser_detected and stopped_time > STOP_DELAY:
            face_recognition_ready()

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
            cv2.putText(
                frame,
                "Mouse moving: Face gesture OFF",
                (30, 75),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )

        # 화면 출력
        cv2.imshow("Laser Mouse Control", frame)

        # 레이저 인식 확인용 마스크
        # 필요하면 아래 주석 해제
        # cv2.imshow("Mask", mask)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q") or key == 27:
            print("종료합니다.")
            break


finally:
    cap.release()
    cv2.destroyAllWindows()
    print("카메라가 꺼졌습니다.")