import cv2
import numpy as np
from collections import deque # 최근 좌표를 저장해서 좌표 흔들림을 줄임


# =========================
# 기본 설정
# =========================
CAMERA_INDEX = 4 #안 되면 0, 1, 2 중 바꿔보기

# 레이저 인식 기준값
R_MIN = 160 # 빨간 채널 최소 밝기
RED_DIFF = 50 # R이 G/B보다 얼마나 더 강해야 하는지

# 레이저 점 크기 조건
MIN_AREA = 10 # 너무 작은 노이즈 제외
MAX_AREA = 5000 # 너무 큰 빨간 덩어리 제외
MAX_W_H = 200 # 가로/세로가 너무 큰 후보 제외


# =========================
# 카메라 열기
# =========================
cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)

if not cap.isOpened():
    print("카메라를 열 수 없습니다.")
    exit()


# =========================
# 좌표 흔들림 보정용 저장공간
# =========================
x_history = deque(maxlen=3)
y_history = deque(maxlen=3)


print("레이저 인식 시작. 종료하려면 q 또는 ESC를 누르세요.")


try:
    while True:
        # =========================
        # 현재 프레임 읽기
        # =========================
        ret, frame = cap.read()

        if not ret:
            print("프레임을 읽을 수 없습니다.")
            break

        # 화면 좌우 반전
        #frame = cv2.flip(frame, 1)

        # BGR 채널 분리
        b, g, r = cv2.split(frame)

        # overflow 방지를 위해 int16으로 변환
        r_i = r.astype(np.int16)
        g_i = g.astype(np.int16)
        b_i = b.astype(np.int16)

        # =========================
        # 레이저다운 픽셀만 남기기
        # =========================
        laser_pixel = (
            (r_i > R_MIN) &
            (r_i > g_i + RED_DIFF) &
            (r_i > b_i + RED_DIFF) 
        )

        # True/False 값을 흰색/검은색 마스크로 변환
        mask = laser_pixel.astype(np.uint8) * 255

        # 작은 노이즈 제거
        mask = cv2.medianBlur(mask, 3)


        # =========================
        # 흰색 덩어리 찾기
        # =========================
        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        best_candidate = None
        best_score = -1


        # =========================
        # 레이저 후보 검사
        # =========================
        for contour in contours:
            # 후보 면적 계산
            area = cv2.contourArea(contour)

            # 너무 작거나 너무 크면 제외
            if not (MIN_AREA < area < MAX_AREA):
                continue

            # 후보를 감싸는 사각형 구하기
            x, y, w, h = cv2.boundingRect(contour)

            # 가로/세로가 너무 크면 제외
            if w > MAX_W_H or h > MAX_W_H:
                continue

            # 너무 길쭉한 모양 제외
            ratio = w / h if h != 0 else 0

            if ratio < 0.4 or ratio > 2.5:
                continue

            # 후보 중심 좌표 계산
            M = cv2.moments(contour)

            if M["m00"] == 0:
                continue

            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

            # 더 빨갛고 밝은 후보를 우선 선택
            score = int(r[cy, cx]) + area

            if score > best_score:
                best_score = score
                best_candidate = {
                    "x": cx,
                    "y": cy
                }


        # =========================
        # 레이저 후보가 있을 때
        # =========================
        if best_candidate is not None:
            raw_x = best_candidate["x"]
            raw_y = best_candidate["y"]

            # 현재 좌표를 저장공간에 넣기
            x_history.append(raw_x)
            y_history.append(raw_y)

            # 최근 3개 좌표의 평균을 내서 흔들림 줄이기
            laser_x = int(sum(x_history) / len(x_history))
            laser_y = int(sum(y_history) / len(y_history))

            print(
                f"Laser: x={laser_x}, y={laser_y}"
            )

            # 레이저 위치에 초록색 원 표시
            cv2.circle(frame, (laser_x, laser_y), 10, (0, 255, 0), 2)

            # 레이저 좌표 텍스트 표시
            cv2.putText(
                frame,
                f"Laser ({laser_x}, {laser_y})",
                (laser_x + 15, laser_y - 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )


        # =========================
        # 레이저 후보가 없을 때
        # =========================
        else:
            # 이전 좌표 기록 삭제
            x_history.clear()
            y_history.clear()


        # =========================
        # 화면 출력
        # =========================
        cv2.imshow("Laser Detection", frame)

        # =========================
        # 종료 키 확인
        # =========================
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q") or key == 27: # q 또는 ESC
            print("종료합니다.")
            break


# =========================
# 종료 처리
# =========================
finally:
    cap.release()
    cv2.destroyAllWindows()
    print("카메라가 꺼졌습니다.")