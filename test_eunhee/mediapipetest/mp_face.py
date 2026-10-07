import cv2
import mediapipe as mp
import numpy as np

mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(max_num_faces=1, refine_landmarks=True)

cap = cv2.VideoCapture(0)

while cap.isOpened():
    success, image = cap.read()
    if not success:
        break

    # 연산 속도를 위해 RGB 변환
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(image_rgb)

    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:
            h, w, _ = image.shape

            # 미디어파이 Face Mesh 기준 왼쪽 눈 고유 번호: 33, 오른쪽 눈: 263
            left_eye = face_landmarks.landmark[33]
            right_eye = face_landmarks.landmark[263]

            # 이미지 픽셀 좌표로 변환
            le_pos = np.array([left_eye.x * w, left_eye.y * h])
            re_pos = np.array([right_eye.x * w, right_eye.y * h])

            # 두 눈 사이의 각도(라디안) 계산 후 도(Degree) 단위 변환
            dy = re_pos[1] - le_pos[1]
            dx = re_pos[0] - le_pos[0]
            angle = np.degrees(np.arctan2(dy, dx))

            # 기준(0도)에서 특정 각도 이상 기울었는지 체크
            if angle > 15:
                status = "Right Tilt (오른쪽 까딱)"
            elif angle < -15:
                status = "Left Tilt (왼쪽 까딱)"
            else:
                status = "Center (정면)"

            cv2.putText(
                image,
                f"Angle: {angle:.1f} | {status}",
                (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
            )

    cv2.imshow("Tilt Detection", image)
    if cv2.waitKey(5) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
