"""클릭, 더블클릭, 우클릭, 스크롤 실행."""

import pyautogui

from config import SCROLL_AMOUNT

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0


def execute_mouse_action(action_id):
    if action_id == "left_single":
        pyautogui.click()
        print("왼쪽 클릭 실행")

    elif action_id == "right_single":
        pyautogui.rightClick()
        print("오른쪽 클릭 실행")

    elif action_id == "left_double":
        pyautogui.doubleClick()
        print("왼쪽 더블클릭 실행")

    elif action_id == "scroll_up":
        pyautogui.scroll(SCROLL_AMOUNT)
        print("스크롤 위 실행")

    elif action_id == "scroll_down":
        pyautogui.scroll(-SCROLL_AMOUNT)
        print("스크롤 아래 실행")

    else:
        print("알 수 없는 동작:", action_id)
