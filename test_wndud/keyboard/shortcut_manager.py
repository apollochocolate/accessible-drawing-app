# shortcut_manager.py

modifier_state = {
    "Ctrl": False,
    "Alt": False,
    "Shift": False
}

last_key = None

def process_key(detected_key):
    global last_key

    if detected_key == last_key:
        return

    if detected_key in ["LCtrl", "RCtrl"]:
        modifier_state["Ctrl"] = not modifier_state["Ctrl"]
        print(f"Ctrl {'ON' if modifier_state['Ctrl'] else 'OFF'}")

    elif detected_key in ["LAlt", "RAlt"]:
        modifier_state["Alt"] = not modifier_state["Alt"]
        print(f"Alt {'ON' if modifier_state['Alt'] else 'OFF'}")

    elif detected_key in ["LShift", "RShift"]:
        modifier_state["Shift"] = not modifier_state["Shift"]
        print(f"Shift {'ON' if modifier_state['Shift'] else 'OFF'}")

    else:
        combo = []

        if modifier_state["Ctrl"]:
            combo.append("Ctrl")

        if modifier_state["Alt"]:
            combo.append("Alt")

        if modifier_state["Shift"]:
            combo.append("Shift")

        combo.append(detected_key)

        print(" + ".join(combo))

    last_key = detected_key
