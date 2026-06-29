# face_input.py
import cv2

def detect_left_click():

    key = cv2.waitKey(1) & 0xFF

    if key == ord(" "):
        return True

    return False


def detect_right_click():

    """
    얼굴인식에서
    우클릭이 발생하면 True
    """

    return False