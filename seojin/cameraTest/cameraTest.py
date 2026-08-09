import cv2
import time

MAX_CAMERAS = 8

print("카메라 번호 테스트 시작")
print("각 카메라 화면이 3초씩 뜹니다.")
print("n: 다음 카메라 / q: 종료")
print("-" * 40)

for idx in range(MAX_CAMERAS):
    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print(f"[카메라 {idx}] 열기 실패")
        cap.release()
        continue

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    ok, frame = cap.read()

    if not ok or frame is None:
        print(f"[카메라 {idx}] 프레임 읽기 실패")
        cap.release()
        continue

    print(f"[카메라 {idx}] 인식됨")

    start = time.time()

    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            break

        cv2.putText(
            frame,
            f"CAMERA {idx}",
            (30, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            (0, 255, 0),
            3,
        )

        cv2.putText(
            frame,
            "n: next / q: quit",
            (30, 110),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
        )

        cv2.imshow("Camera Test", frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            cap.release()
            cv2.destroyAllWindows()
            print("테스트 종료")
            exit()

        if key == ord("n"):
            break

        if time.time() - start > 3:
            break

    cap.release()

cv2.destroyAllWindows()
print("-" * 40)
print("테스트 완료")