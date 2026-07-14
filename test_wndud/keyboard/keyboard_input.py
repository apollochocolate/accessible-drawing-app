from pynput.keyboard import Controller, Key

keyboard = Controller()

shift_mode = False
caps_mode = False
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

SHIFT_NUMBER = {
    "1":"!",
    "2":"@",
    "3":"#",
    "4":"$",
    "5":"%",
    "6":"^",
    "7":"&",
    "8":"*",
    "9":"(",
    "0":")",
    "-":"_",
    "=":"+",
    "[":"{",
    "]":"}",
    "\\":"|",
    ";":":",
    "'":"\"",
    ",":"<",
    ".":">",
    "/":"?",
    "`":"~"
}

# ==========================
# 일반 키 입력
# ==========================
def press_key(key):

    global shift_mode
    global caps_mode

    if key is None:
        return

    # Shift
    if key in ["Shift", "LShift", "RShift"]:
        shift_mode = not shift_mode
        print("Shift :", shift_mode)
        return

    # Caps
    if key == "Caps":
        caps_mode = not caps_mode
        print("Caps :", caps_mode)
        return

    # 알파벳
    if len(key) == 1 and key.isalpha():

        upper = shift_mode ^ caps_mode

        ch = key.upper() if upper else key.lower()

        keyboard.press(ch)
        keyboard.release(ch)

        if shift_mode:
            shift_mode = False

        return

# ==========================
# 단축키 입력
# ==========================
def press_shortcut(modifier, key):

    if modifier not in MODIFIER:
        return

    keyboard.press(MODIFIER[modifier])

    if len(key) == 1:

        if shift_mode and key in SHIFT_NUMBER:
            keyboard.type(SHIFT_NUMBER[key])
            shift_mode = False
            return

        keyboard.type(key)

    if shift_mode:
        shift_mode = False

    return
    