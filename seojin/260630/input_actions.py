"""
input_actions.py
실제 OS 입력 실행 담당.
- 레이저 키보드 영역의 키 입력
- 레이저 마우스 영역의 커서 이동
- 얼굴 제스처의 클릭/스크롤 실행
"""

import time
import pyautogui

from config_combined import WIN_W, WIN_H, MOUSE_ZONE_Y

screen_w, screen_h = pyautogui.size()
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

KEY_INPUT_COOLDOWN = 0.35
KEY_MODIFIER_TIMEOUT = 5.0

MODIFIER_KEYS = {"Ctrl", "LShift", "RShift", "Alt", "Win"}
CTRL_ALLOWED_KEYS = {"C", "V", "A", "Z", "F", "S"}
SHIFT_ALLOWED_KEYS = {"Up", "Down", "Left", "Right"}
ALT_ALLOWED_KEYS = {"Tab"}
WIN_ALLOWED_KEYS = {"Up", "Down", "Left", "Right"}

KEY_NAME_TO_PYAUTO = {
    "Esc": "esc",
    "BkSp": "backspace",
    "Tab": "tab",
    "Caps": "capslock",
    "Enter": "enter",
    "Space": "space",
    "PrtScr": "printscreen",
    "Ins": "insert",
    "Del": "delete",
    "Up": "up",
    "Down": "down",
    "Left": "left",
    "Right": "right",
    "`": "`",
    "-": "-",
    "=": "=",
    "[": "[",
    "]": "]",
    "\\": "\\",
    ";": ";",
    "'": "'",
    ",": ",",
    ".": ".",
    "/": "/",
}

for _ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    KEY_NAME_TO_PYAUTO[_ch] = _ch.lower()
for _ch in "0123456789":
    KEY_NAME_TO_PYAUTO[_ch] = _ch
for _i in range(1, 13):
    KEY_NAME_TO_PYAUTO[f"F{_i}"] = f"f{_i}"


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
        print("왼쪽 클릭 실행")
    elif action_id == "right_single":
        pyautogui.rightClick()
        print("오른쪽 클릭 실행")
    elif action_id == "left_double":
        pyautogui.doubleClick()
        print("왼쪽 더블클릭 실행")
    elif action_id == "scroll_up":
        pyautogui.scroll(5)
        print("스크롤 위 실행")
    elif action_id == "scroll_down":
        pyautogui.scroll(-5)
        print("스크롤 아래 실행")
    else:
        print("알 수 없는 동작:", action_id)


class KeyboardInputController:
    def __init__(self):
        self.active_modifier = None
        self.modifier_start_time = None
        self.current_hover_key = None
        self.last_input_time = 0.0

    def reset_hover(self):
        self.current_hover_key = None

    def clear_modifier(self):
        self.active_modifier = None
        self.modifier_start_time = None

    def _normalize_modifier_key(self, key):
        if key == "Ctrl":
            return "ctrl"
        if key in {"LShift", "RShift", "Shift"}:
            return "shift"
        if key == "Alt":
            return "alt"
        if key == "Win":
            return "win"
        return key.lower()

    def _display_modifier_name(self, key):
        if key == "Ctrl":
            return "Ctrl"
        if key in {"LShift", "RShift"}:
            return "Shift"
        if key == "Alt":
            return "Alt"
        if key == "Win":
            return "Win"
        return key

    def _allowed_keys(self, modifier_name):
        if modifier_name == "Ctrl":
            return CTRL_ALLOWED_KEYS
        if modifier_name == "Shift":
            return SHIFT_ALLOWED_KEYS
        if modifier_name == "Alt":
            return ALT_ALLOWED_KEYS
        if modifier_name == "Win":
            return WIN_ALLOWED_KEYS
        return set()

    def _key_to_pyautogui_name(self, key):
        return KEY_NAME_TO_PYAUTO.get(key)

    def _send_key(self, key):
        if key in {"Fn", "한자 ", "한자", "한/영"}:
            print(f"[UNSUPPORTED KEY] {key}")
            return
        py_key = self._key_to_pyautogui_name(key)
        if py_key is None:
            print(f"[UNKNOWN KEY] {key}")
            return
        pyautogui.press(py_key)
        print(f"[KEY] {key}")

    def process_key(self, detected_key):
        if detected_key is None:
            return

        now = time.time()

        if self.active_modifier is not None and self.modifier_start_time is not None:
            if now - self.modifier_start_time > KEY_MODIFIER_TIMEOUT:
                print("[MOD TIMEOUT]")
                self.clear_modifier()

        # 같은 키 위에 계속 머무를 때 반복 입력 방지
        if detected_key == self.current_hover_key:
            return

        if now - self.last_input_time < KEY_INPUT_COOLDOWN:
            self.current_hover_key = detected_key
            return

        self.current_hover_key = detected_key

        if detected_key in MODIFIER_KEYS:
            self.active_modifier = self._display_modifier_name(detected_key)
            self.modifier_start_time = now
            self.last_input_time = now
            print(f"[MOD SET] {self.active_modifier}")
            return

        if self.active_modifier is not None:
            allowed = self._allowed_keys(self.active_modifier)
            if detected_key in allowed:
                mod_key = self._normalize_modifier_key(self.active_modifier)
                py_key = self._key_to_pyautogui_name(detected_key)
                if py_key:
                    pyautogui.hotkey(mod_key, py_key)
                    print(f"[HOTKEY] {self.active_modifier}+{detected_key}")
                self.clear_modifier()
                self.last_input_time = now
            return

        self._send_key(detected_key)
        self.last_input_time = now
