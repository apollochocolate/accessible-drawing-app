import cv2
import numpy as np

# ── 설정 상수 ───────────────────────────────────────────────
RESULT_WIDTH  = 640
RESULT_HEIGHT = 480
CAM_WIDTH     = 640
CAM_HEIGHT    = 480
TARGET_IDS    = [1, 2, 3, 4]   # 좌상, 우상, 좌하, 우하
MARKER_RADIUS = 5

# dst 좌표: ID 순서 1(좌상) → 2(우상) → 3(좌하) → 4(우하)
DST_PTS = np.float32([
    [0,            0           ],  # 1: 좌상
    [RESULT_WIDTH, 0           ],  # 2: 우상
    [RESULT_WIDTH, RESULT_HEIGHT], # 4: 우하
    [0,            RESULT_HEIGHT], # 3: 좌하
])

# ── 유틸 함수 ───────────────────────────────────────────────

def get_marker_centers(corners, ids):
    """검출된 마커에서 {id: (cx, cy)} 딕셔너리 반환"""
    centers = {}
    for i, marker_id in enumerate(ids.flatten()):
        if marker_id in TARGET_IDS:
            pts = corners[i][0]                        # shape (4, 2)
            cx, cy = np.mean(pts, axis=0).astype(int)  # 한 번에 계산
            centers[int(marker_id)] = (int(cx), int(cy))
    return centers


def draw_marker_info(frame, marker_centers):
    """마커 중심점과 ID 텍스트를 프레임에 그림"""
    for marker_id, (cx, cy) in marker_centers.items():
        cv2.circle(frame, (cx, cy), MARKER_RADIUS, (0, 255, 0), -1)
        cv2.putText(
            frame, f"ID {marker_id}",
            (cx + 10, cy),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2
        )


def overlay_status(frame, text, color):
    """화면 좌상단에 상태 텍스트 출력"""
    cv2.putText(
        frame, text,
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2
    )


def warp_perspective(frame, marker_centers):
    """
    4개 마커 중심을 이용해 원근 변환 수행.
    배치:  1 2
           3 4
    반환: warped 이미지 (변환 실패 시 검은 화면)
    """
    src_pts = np.float32([
        marker_centers[1],  # 좌상
        marker_centers[2],  # 우상
        marker_centers[4],  # 우하
        marker_centers[3],  # 좌하
    ])

    matrix = cv2.getPerspectiveTransform(src_pts, DST_PTS)
    return cv2.warpPerspective(frame, matrix, (RESULT_WIDTH, RESULT_HEIGHT))


# ── 초기화 ──────────────────────────────────────────────────

def create_detector():
    aruco_dict   = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    aruco_params = cv2.aruco.DetectorParameters()
    return cv2.aruco.ArucoDetector(aruco_dict, aruco_params)


def open_camera(index=0):
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        raise RuntimeError(f"카메라 {index}번을 열 수 없습니다.")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAM_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
    return cap


# ── 메인 루프 ───────────────────────────────────────────────

def main():
    detector = create_detector()
    cap = open_camera(0)

    print("AruCo 실시간 원근 보정 시작")
    print("마커 배치:  1 2")
    print("           3 4")
    print("종료: q")

    # 검은 화면 한 번만 생성 (warp 실패 시 재사용)
    blank = np.zeros((RESULT_HEIGHT, RESULT_WIDTH, 3), dtype=np.uint8)
    warped_img = blank.copy()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("카메라 읽기 실패")
                break

            corners, ids, _ = detector.detectMarkers(frame)
            clean_frame = frame.copy()  # 오버레이 없는 원본 보존

            if ids is not None:
                cv2.aruco.drawDetectedMarkers(frame, corners, ids)
                marker_centers = get_marker_centers(corners, ids)
                draw_marker_info(frame, marker_centers)

                if all(k in marker_centers for k in TARGET_IDS):
                    warped_img = warp_perspective(clean_frame, marker_centers)
                    overlay_status(frame, "Status: Warping Active", (0, 255, 0))
                else:
                    detected = sorted(marker_centers.keys())
                    missing  = sorted(set(TARGET_IDS) - set(detected))
                    overlay_status(frame, f"Missing IDs: {missing}", (0, 0, 255))
                    warped_img = blank.copy()
            else:
                overlay_status(frame, "No markers detected", (0, 0, 255))
                warped_img = blank.copy()

            cv2.imshow("Webcam Stream", frame)
            cv2.imshow("Birds Eye View", warped_img)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        # 예외가 발생해도 반드시 자원 해제
        cap.release()
        cv2.destroyAllWindows()
        print("종료")


if __name__ == "__main__":
    main()