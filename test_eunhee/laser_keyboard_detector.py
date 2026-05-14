import cv2
import numpy as np

# ===== 1. 키보드 좌표 설정 (정규화된 평면) =====
# (단순 예시: QWERTY 일부 영역만 정의)
key_map = {
    "Q": (50, 50, 100, 100),
    "W": (150, 50, 200, 100),
    "E": (250, 50, 300, 100),
    "A": (75, 120, 125, 170),
    "S": (175, 120, 225, 170),
    "D": (275, 120, 325, 170),
}

# ===== 2. 마우스로 키보드 4점 찍기 =====
points = []

def mouse_callback(event, x, y, flags, param):
    global points
    if event == cv2.EVENT_LBUTTONDOWN:
        if len(points) < 4:
            points.append([x, y])
            print(f"Point {len(points)}: {x}, {y}")

# ===== 3. 레이저(빨간 점) 검출 =====
def detect_laser(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    lower_red1 = np.array([0, 120, 120])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 120, 120])
    upper_red2 = np.array([180, 255, 255])

    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask = mask1 + mask2

    mask = cv2.GaussianBlur(mask, (9, 9), 0)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        c = max(contours, key=cv2.contourArea)
        if cv2.contourArea(c) > 50:
            (x, y), radius = cv2.minEnclosingCircle(c)
            return int(x), int(y)
    return None

# ===== 4. 키 판별 =====
def find_key(x, y):
    for key, (x1, y1, x2, y2) in key_map.items():
        if x1 <= x <= x2 and y1 <= y <= y2:
            return key
    return None

# ===== 5. 메인 =====
cap = cv2.VideoCapture(0)
cv2.namedWindow("frame")
cv2.setMouseCallback("frame", mouse_callback)

H = None

while True:
    ret, frame = cap.read()
    if not ret:
        break

    display = frame.copy()

    # 4점 선택 전
    if len(points) < 4:
        for p in points:
            cv2.circle(display, tuple(p), 5, (0,255,0), -1)
        cv2.putText(display, "Click 4 corners of keyboard", (10,30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)

    # Homography 계산
    elif H is None:
        pts_src = np.array(points, dtype=np.float32)
        pts_dst = np.array([[0,0],[400,0],[400,300],[0,300]], dtype=np.float32)
        H = cv2.getPerspectiveTransform(pts_src, pts_dst)
        print("Homography calculated")

    else:
        warped = cv2.warpPerspective(frame, H, (400,300))

        laser = detect_laser(frame)

        if laser:
            lx, ly = laser

            # 좌표 변환
            pt = np.array([[[lx, ly]]], dtype=np.float32)
            transformed = cv2.perspectiveTransform(pt, H)
            tx, ty = int(transformed[0][0][0]), int(transformed[0][0][1])

            key = find_key(tx, ty)

            cv2.circle(display, (lx, ly), 10, (0,0,255), 2)

            if key:
                cv2.putText(display, f"KEY: {key}", (lx, ly-20),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)

        cv2.imshow("warped", warped)

    cv2.imshow("frame", display)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
