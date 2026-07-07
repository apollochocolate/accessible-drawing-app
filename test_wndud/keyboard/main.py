# main.py

import cv2
import numpy as np
# from mode_manager import (
#     process_mode_key,
#     is_laser_only_mode
# )
from keyboard_listener import start_keyboard_listener
from keyboard_layout import KEY_MAP
from laser_detect import detect_red_laser
from renderer import draw_keyboard_overlay
from face_input import detect_left_click
from input_controller import InputController

WIN_W = 640
WIN_H = 480


def get_key_at(x, y):
    for name, (x1, y1, x2, y2) in KEY_MAP.items():
        if x1 <= x <= x2 and y1 <= y <= y2:
            return name
    return None


TUNE_WIN = "[ HSV Tuning ] - q:quit  m:mask on/off"

cv2.namedWindow(TUNE_WIN)
cv2.resizeWindow(TUNE_WIN, 600, 350)

cv2.createTrackbar("H_low1",  TUNE_WIN, 0,   10,  lambda x: None)
cv2.createTrackbar("H_high1", TUNE_WIN, 10,  30,  lambda x: None)

cv2.createTrackbar("H_low2",  TUNE_WIN, 160, 180, lambda x: None)
cv2.createTrackbar("H_high2", TUNE_WIN, 180, 180, lambda x: None)

cv2.createTrackbar("S_min",   TUNE_WIN, 80,  255, lambda x: None)
cv2.createTrackbar("V_min",   TUNE_WIN, 100, 255, lambda x: None)

cv2.createTrackbar("Blur",    TUNE_WIN, 5,   21,  lambda x: None)
cv2.createTrackbar("Area",    TUNE_WIN, 5,   200, lambda x: None)


cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
controller = InputController()
start_keyboard_listener(controller)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIN_W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WIN_H)

for _ in range(10):
    cap.read()


show_mask = False

print("실행 중...")
print("q : 종료")
print("m : 마스크 ON/OFF")


while True:

    ret, frame = cap.read()

    if not ret or frame is None or frame.size == 0:
        frame = np.zeros((WIN_H, WIN_W, 3), dtype=np.uint8)

    frame = cv2.resize(frame, (WIN_W, WIN_H))


    h_lo   = cv2.getTrackbarPos("H_low1",  TUNE_WIN)
    h_hi   = cv2.getTrackbarPos("H_high1", TUNE_WIN)

    h_lo2  = cv2.getTrackbarPos("H_low2",  TUNE_WIN)
    h_hi2  = cv2.getTrackbarPos("H_high2", TUNE_WIN)

    s_min  = cv2.getTrackbarPos("S_min",   TUNE_WIN)
    v_min  = cv2.getTrackbarPos("V_min",   TUNE_WIN)

    blur_k = max(cv2.getTrackbarPos("Blur", TUNE_WIN), 1)
    area_m = cv2.getTrackbarPos("Area", TUNE_WIN)


    cx, cy, mask = detect_red_laser(
        frame,
        h_lo,
        h_hi,
        h_lo2,
        h_hi2,
        s_min,
        v_min,
        blur_k,
        area_m
    )

    detected_key = None
    #current_mode = is_laser_only_mode()

    
    if cx is not None:

        detected_key = get_key_at(cx, cy)

        

    controller.update_hover(detected_key)

    draw_keyboard_overlay(
        frame,
        KEY_MAP,
        detected_key,
    ) 
    
    
    cv2.imshow("Laser Keyboard", frame)

    if show_mask:
        cv2.imshow("Mask Debug", mask)

    
    key = cv2.waitKey(1) & 0xFF

    if detect_left_click(key):
        controller.left_click()

    if key == ord("q"):
        break

    elif key == ord("m"):

        show_mask = not show_mask

        if not show_mask:
            cv2.destroyWindow("Mask Debug")
        print(f"마스크 창: {'ON' if show_mask else 'OFF'}")


cap.release()

cv2.destroyAllWindows()
