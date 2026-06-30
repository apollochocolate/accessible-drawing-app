from pynput.keyboard import Controller, Key

keyboard = Controller()


# ==========================
# 특수키
# ==========================
SPECIAL = {
    "Space": Key.space,
    "Enter": Key.enter,
    "Backspace": Key.backspace,
    "Tab": Key.tab,
    "Esc": Key.esc,
    "Up": Key.up,
    "Down": Key.down,
    "Left": Key.left,
    "Right": Key.right
}


# ==========================
# Modifier
# ==========================
MODIFIER = {
    "Ctrl": Key.ctrl,
    "Shift": Key.shift,
    "Alt": Key.alt,
    "Win": Key.cmd
}


# ==========================
# 일반 키 입력
# ==========================
def press_key(key):

    if key is None:
        return

    # 알파벳
    if len(key) == 1:
        keyboard.press(key.lower())
        keyboard.release(key.lower())
        return

    # 특수키
    if key in SPECIAL:
        keyboard.press(SPECIAL[key])
        keyboard.release(SPECIAL[key])


# ==========================
# 단축키 입력
# ==========================
def press_shortcut(modifier, key):

    if modifier not in MODIFIER:
        return

    keyboard.press(MODIFIER[modifier])

    if len(key) == 1:
        keyboard.press(key.lower())
        keyboard.release(key.lower())

    elif key in SPECIAL:
        keyboard.press(SPECIAL[key])
        keyboard.release(SPECIAL[key])

    keyboard.release(MODIFIER[modifier])
    