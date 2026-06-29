from pynput.keyboard import Controller, Key

keyboard = Controller()


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


def press_key(key):

    if key is None:
        return

    if len(key) == 1:
        keyboard.type(key.lower())
        return

    if key in SPECIAL:
        keyboard.press(SPECIAL[key])
        keyboard.release(SPECIAL[key])


def press_shortcut(modifier, key):

    MOD = {
        "Ctrl": Key.ctrl,
        "Shift": Key.shift,
        "Alt": Key.alt,
        "Win": Key.cmd
    }

    keyboard.press(MOD[modifier])

    if key in SPECIAL:
        keyboard.press(SPECIAL[key])
        keyboard.release(SPECIAL[key])
    else:
        keyboard.press(key.lower())
        keyboard.release(key.lower())

    keyboard.release(MOD[modifier])