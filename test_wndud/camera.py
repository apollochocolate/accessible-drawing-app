import cv2

for i in range(10):
    cap = cv2.VideoCapture(i)

    if cap.isOpened():
        print(f"카메라 {i} 열림!")

        ret, frame = cap.read()

        if ret:
            cv2.imshow(f"cam{i}", frame)
            cv2.waitKey(3000)

        cap.release()
    else:
        print(f"카메라 {i} 실패")