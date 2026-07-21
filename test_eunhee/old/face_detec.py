import cv2
import time
from collections import deque

# 눈깜빡임 + 얼굴 기울기(고개 까딱)

# Load Haar Cascade files
face_cascade = cv2.CascadeClassifier("haarcascade_frontalface_default.xml")

eye_cascade = cv2.CascadeClassifier("haarcascade_eye_tree_eyeglasses.xml")

print("Face cascade:", not face_cascade.empty())
print("Eye cascade:", not eye_cascade.empty())

# Open webcam
cap = cv2.VideoCapture(0)

# Lower resolution for Raspberry Pi
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

# ── 눈 깜빡임 상태 ──────────────────────────────────────────
left_eye_detected = True
right_eye_detected = True

left_missing_start = None
right_missing_start = None

BLINK_TIME = 0.15  # 눈 감은 상태가 이 시간(초) 이상 지속되면 깜빡임으로 판정

# ── 고개 까딱 감지 설정 ─────────────────────────────────────
# 얼굴 중심 X 좌표 이력 (deque로 최근 N 프레임 유지)
HISTORY_LEN = 12  # 분석할 프레임 수
face_cx_history = deque(maxlen=HISTORY_LEN)

TILT_THRESHOLD = 18  # 이동 거리(px) 기준: 이보다 크면 까딱으로 판정
TILT_COOLDOWN = 0.8  # 연속 감지 방지 쿨다운(초)

last_tilt_time = 0
last_tilt_dir = None  # 마지막 까딱 방향 표시용
tilt_display_end = 0  # 화면에 텍스트를 보여줄 종료 시각


# ── 고개 까딱 분석 함수 ─────────────────────────────────────
def detect_head_tilt(history, threshold):
    """
    history: deque of face center X values (most recent = rightmost)
    returns: 'LEFT', 'RIGHT', or None

    감지 방식:
      - 최근 절반 평균(끝)  vs  이전 절반 평균(앞) 비교
      - 차이가 threshold 이상이면 방향 반환
    """
    if len(history) < HISTORY_LEN:
        return None

    vals = list(history)
    half = HISTORY_LEN // 2
    prev_avg = sum(vals[:half]) / half
    curr_avg = sum(vals[half:]) / half

    diff = curr_avg - prev_avg

    if diff > threshold:
        return "RIGHT"  # 화면 기준 오른쪽 (미러 플립 상태이므로 실제 왼쪽)
    elif diff < -threshold:
        return "LEFT"  # 화면 기준 왼쪽  (실제 오른쪽)
    return None


# ── 메인 루프 ───────────────────────────────────────────────
while True:

    ret, frame = cap.read()

    if not ret:
        print("Camera error")
        break

    # 좌우 반전
    frame = cv2.flip(frame, 1)

    # 그레이스케일 변환 & 대비 향상
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    # 얼굴 감지
    faces = face_cascade.detectMultiScale(
        gray, scaleFactor=1.15, minNeighbors=5, minSize=(80, 80)
    )

    current_time = time.time()
    face_found = False

    for x, y, w, h in faces:

        face_found = True

        # 얼굴 중심 X 좌표 이력에 추가
        face_cx = x + w // 2
        face_cx_history.append(face_cx)

        # 얼굴 사각형 그리기
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

        # 얼굴 중심점 표시 (참고용)
        cv2.circle(frame, (face_cx, y + h // 2), 3, (255, 100, 0), -1)

        # ── 고개 까딱 감지 ──────────────────────────────
        if current_time - last_tilt_time > TILT_COOLDOWN:
            direction = detect_head_tilt(face_cx_history, TILT_THRESHOLD)
            if direction:
                last_tilt_time = current_time
                last_tilt_dir = direction
                tilt_display_end = current_time + 0.8  # 0.8초 동안 표시
                print(f"HEAD TILT {direction}")

        # ── 눈 감지 ──────────────────────────────────────
        face_gray = gray[y : y + h, x : x + w]
        face_color = frame[y : y + h, x : x + w]

        eyes = eye_cascade.detectMultiScale(
            face_gray, scaleFactor=1.03, minNeighbors=2, minSize=(10, 10)
        )

        eye_data = []
        for ex, ey, ew, eh in eyes:
            if ey > h // 2:
                continue
            cx = ex + ew // 2
            eye_data.append((cx, ex, ey, ew, eh))

        eye_data = sorted(eye_data, key=lambda e: e[0])

        # LEFT EYE
        if len(eye_data) >= 1:
            _, ex, ey, ew, eh = eye_data[0]
            cv2.rectangle(face_color, (ex, ey), (ex + ew, ey + eh), (0, 255, 0), 2)
            left_eye_detected = True
            left_missing_start = None
        else:
            if left_missing_start is None:
                left_missing_start = current_time
            elif current_time - left_missing_start > BLINK_TIME:
                cv2.putText(
                    frame,
                    "LEFT EYE BLINK",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2,
                )
                print("LEFT EYE BLINK")
                left_missing_start = current_time + 999

        # RIGHT EYE
        if len(eye_data) >= 2:
            _, ex, ey, ew, eh = eye_data[1]
            cv2.rectangle(face_color, (ex, ey), (ex + ew, ey + eh), (0, 255, 255), 2)
            right_eye_detected = True
            right_missing_start = None
        else:
            if right_missing_start is None:
                right_missing_start = current_time
            elif current_time - right_missing_start > BLINK_TIME:
                cv2.putText(
                    frame,
                    "RIGHT EYE BLINK",
                    (20, 80),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 0, 0),
                    2,
                )
                print("RIGHT EYE BLINK")
                right_missing_start = current_time + 999

        # 첫 번째 얼굴만 처리
        break

    # 얼굴이 없으면 이력 초기화 (오탐 방지)
    if not face_found:
        face_cx_history.clear()

    # ── 고개 까딱 텍스트 표시 ────────────────────────────────
    if last_tilt_dir and current_time < tilt_display_end:
        arrow = "◀ LEFT" if last_tilt_dir == "LEFT" else "RIGHT ▶"
        color = (0, 200, 255) if last_tilt_dir == "LEFT" else (255, 200, 0)
        cv2.putText(
            frame,
            f"HEAD TILT {arrow}",
            (20, 130),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            color,
            2,
        )

    # 프레임 출력
    cv2.imshow("Blink & Head Tilt Detection", frame)

    if cv2.waitKey(1) == 27:  # ESC
        break

# 정리
cap.release()
cv2.destroyAllWindows()
