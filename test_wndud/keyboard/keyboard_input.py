# keyboard_input.py

from pynput.keyboard import Controller, Key

keyboard = Controller()


def input_key(key):

    # -----------------------
    # 문자
    # -----------------------
    if len(key) == 1:
        keyboard.type(key.lower())
        return

    # -----------------------
    # 특수키
    # -----------------------
    special = {
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

    if key in special:
        keyboard.press(special[key])
        keyboard.release(special[key])


def input_shortcut(modifier, key):

    modifier_map = {
        "Ctrl": Key.ctrl,
        "Shift": Key.shift,
        "Alt": Key.alt,
        "Win": Key.cmd
    }

    special = {
        "Up": Key.up,
        "Down": Key.down,
        "Left": Key.left,
        "Right": Key.right,
        "Tab": Key.tab
    }

    mod = modifier_map.get(modifier)

    if mod is None:
        return

    keyboard.press(mod)

    if key in special:
        keyboard.press(special[key])
        keyboard.release(special[key])
    else:
        keyboard.press(key.lower())
        keyboard.release(key.lower())

    keyboard.release(mod)