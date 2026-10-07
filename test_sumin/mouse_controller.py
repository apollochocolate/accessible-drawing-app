"""구분선 아래 마우스 영역의 이동과 얼굴 제스처 마우스 동작 담당."""

import pyautogui

from config_combined import WIN_W, WIN_H, MOUSE_ZONE_Y

screen_w, screen_h = pyautogui.size()
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0


def mouse_zone_to_screen(x, y):
    rel_x = x / WIN_W
    mouse_zone_h = max(WIN_H - MOUSE_ZONE_Y, 1)
    rel_y = (y - MOUSE_ZONE_Y) / mouse_zone_h

    rel_x = max(0.0, min(1.0, rel_x))
    rel_y = max(0.0, min(1.0, rel_y))

    screen_x = int(rel_x * screen_w)
    screen_y = int(rel_y * screen_h)

    screen_x = max(0, min(screen_w - 1, screen_x))
    screen_y = max(0, min(screen_h - 1, screen_y))
    return screen_x, screen_y


def move_mouse_to(x, y):
    pyautogui.moveTo(x, y)


def execute_mouse_action(action_id):
    if action_id == "left_single":
        pyautogui.click()
        print("[MOUSE] 왼쪽 클릭")
    elif action_id == "right_single":
        pyautogui.rightClick()
        print("[MOUSE] 오른쪽 클릭")
    elif action_id == "left_double":
        pyautogui.doubleClick()
        print("[MOUSE] 더블클릭")
    elif action_id == "scroll_up":
        pyautogui.scroll(5)
        print("[MOUSE] 스크롤 위")
    elif action_id == "scroll_down":
        pyautogui.scroll(-5)
        print("[MOUSE] 스크롤 아래")
