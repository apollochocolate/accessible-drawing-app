import cv2

for i in range(6):
    cap = cv2.VideoCapture(i, cv2.CAP_V4L2)

    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            print(f"Camera index {i}: 열림, frame size = {frame.shape}")
        else:
            print(f"Camera index {i}: 열리지만 프레임 못 읽음")
    else:
        print(f"Camera index {i}: 안 열림")

    cap.release()