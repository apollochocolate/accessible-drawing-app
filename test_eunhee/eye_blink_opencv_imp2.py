import cv2
import time

# Load Haar Cascade files
face_cascade = cv2.CascadeClassifier(
    "haarcascade_frontalface_default.xml"
)

eye_cascade = cv2.CascadeClassifier(
    "haarcascade_eye_tree_eyeglasses.xml"
)

print("Face cascade:", not face_cascade.empty())
print("Eye cascade:", not eye_cascade.empty())

# Open webcam
cap = cv2.VideoCapture(0)

# Lower resolution for Raspberry Pi
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

# Blink states
left_eye_detected = True
right_eye_detected = True

left_missing_start = None
right_missing_start = None

# Blink detection delay
BLINK_TIME = 0.15

while True: 

    ret, frame = cap.read()

    if not ret:
        print("Camera error")
        break

    # Flip image
    frame = cv2.flip(frame, 1)

    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Improve contrast
    gray = cv2.equalizeHist(gray)

    # Detect faces
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.15,
        minNeighbors=5,
        minSize=(80, 80)
    )

    for (x, y, w, h) in faces:

        # Draw face rectangle
        cv2.rectangle(
            frame,
            (x, y),
            (x + w, y + h),
            (255, 0, 0),
            2
        )

        # Face ROI
        face_gray = gray[y:y+h, x:x+w]
        face_color = frame[y:y+h, x:x+w]

        # Detect eyes
        eyes = eye_cascade.detectMultiScale(
            face_gray,
            scaleFactor=1.03,
            minNeighbors=2,
            minSize=(10, 10)
        )

        eye_data = []

        # Collect eye positions
        for (ex, ey, ew, eh) in eyes:

            # Ignore lower face detections
            if ey > h // 2:
                continue

            cx = ex + ew // 2

            eye_data.append((cx, ex, ey, ew, eh))

        # Sort by x position
        eye_data = sorted(eye_data, key=lambda e: e[0])

        current_time = time.time()

        # LEFT EYE
        if len(eye_data) >= 1:

            _, ex, ey, ew, eh = eye_data[0]

            cv2.rectangle(
                face_color,
                (ex, ey),
                (ex + ew, ey + eh),
                (0, 255, 0),
                2
            )

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
                    2
                )

                print("LEFT EYE BLINK")

                left_missing_start = current_time + 999

        # RIGHT EYE
        if len(eye_data) >= 2:

            _, ex, ey, ew, eh = eye_data[1]

            cv2.rectangle(
                face_color,
                (ex, ey),
                (ex + ew, ey + eh),
                (0, 255, 255),
                2
            )

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
                    2
                )

                print("RIGHT EYE BLINK")

                right_missing_start = current_time + 999

    # Show frame
    cv2.imshow("Blink Detection", frame)

    # ESC to exit
    key = cv2.waitKey(1)

    if key == 27:
        break

# Cleanup
cap.release()
cv2.destroyAllWindows()
