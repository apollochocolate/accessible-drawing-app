import cv2

# 카메라 비율 측정
cap = cv2.VideoCapture(0)
while True:
    ret, frame = cap.read()
    if not ret:
        break
    h, w = frame.shape[:2]
    ratio = w / h
    cv2.putText(
        frame,
        f"{w}x{h} ({ratio:.2f})",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 0),
        2,
    )
    cv2.imshow("Webcam", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break
cap.release()
cv2.destroyAllWindows()
