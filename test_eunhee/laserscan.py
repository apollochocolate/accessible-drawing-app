import cv2
import numpy as np
from collections import deque  # Store recent coordinates to reduce jitter


# =========================
# Basic Settings
# =========================
CAMERA_INDEX = 0  # If it doesn't work, run camera_test.py to check index

# Laser detection thresholds
R_MIN = 160  # Minimum brightness for red channel
RED_DIFF = 60  # How much stronger R should be than G/B

# Laser spot size conditions
MIN_AREA = 10    # Exclude very small noise
MAX_AREA = 5000  # Exclude very large red blobs
MAX_W_H = 200    # Exclude candidates with too large width/height


# =========================
# Open Camera
# =========================
cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)

if not cap.isOpened():
    print("Cannot open camera.")
    exit()


# =========================
# Storage for smoothing coordinates
# =========================
x_history = deque(maxlen=3)
y_history = deque(maxlen=3)


print("Laser detection started. Press q or ESC to quit.")
print("In the Mask window, the laser spot should appear white.")


try:
    while True:
        # =========================
        # Read current frame
        # =========================
        ret, frame = cap.read()

        if not ret:
            print("Cannot read frame.")
            break

        # Flip horizontally (optional)
        # frame = cv2.flip(frame, 1)

        # Copy for display
        # display = frame.copy()

        # Split BGR channels
        b, g, r = cv2.split(frame)

        # Convert to int16 to prevent overflow
        r_i = r.astype(np.int16)
        g_i = g.astype(np.int16)
        b_i = b.astype(np.int16)

        # =========================
        # Keep only laser-like pixels
        # =========================
        laser_pixel = (
            (r_i > R_MIN) &
            (r_i > g_i + RED_DIFF) &
            (r_i > b_i + RED_DIFF)
        )

        # Convert True/False mask to white/black image
        mask = laser_pixel.astype(np.uint8) * 255

        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # Remove small noise
        mask = cv2.medianBlur(mask, 3)


        # =========================
        # Find white blobs
        # =========================
        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        best_candidate = None
        best_score = -1


        # =========================
        # Evaluate laser candidates
        # =========================
        for contour in contours:
            # Calculate area
            area = cv2.contourArea(contour)

            # Exclude too small or too large
            if not (MIN_AREA < area < MAX_AREA):
                continue

            # Bounding rectangle
            x, y, w, h = cv2.boundingRect(contour)

            # Exclude if too wide/tall
            if w > MAX_W_H or h > MAX_W_H:
                continue

            # Exclude elongated shapes
            ratio = w / h if h != 0 else 0

            if ratio < 0.4 or ratio > 2.5:
                continue

            # Calculate center point
            M = cv2.moments(contour)

            if M["m00"] == 0:
                continue

            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

            # Prefer brighter and more "red" candidates
            score = int(r[cy, cx]) + area

            if score > best_score:
                best_score = score
                best_candidate = {
                    "x": cx,
                    "y": cy
                }


        # =========================
        # If a laser candidate is found
        # =========================
        if best_candidate is not None:
            raw_x = best_candidate["x"]
            raw_y = best_candidate["y"]

            # Store current coordinates
            x_history.append(raw_x)
            y_history.append(raw_y)

            # Average recent coordinates to reduce jitter
            laser_x = int(sum(x_history) / len(x_history))
            laser_y = int(sum(y_history) / len(y_history))

            print(f"Laser: x={laser_x}, y={laser_y}")

            # Draw green circle at laser position
            cv2.circle(frame, (laser_x, laser_y), 10, (0, 255, 0), 2)

            # Display coordinates text
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
        # If no laser candidate is found
        # =========================
        else:
            # Clear previous coordinate history
            x_history.clear()
            y_history.clear()


        # =========================
        # Display screen
        # =========================
        cv2.imshow("Laser Detection", frame)
        # cv2.imshow("Mask", mask)


        # =========================
        # Check for exit key
        # =========================
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q") or key == 27:  # q or ESC
            print("Exiting.")
            break


# =========================
# Cleanup
# =========================
finally:
    cap.release()
    cv2.destroyAllWindows()
    print("Camera has been released.")
