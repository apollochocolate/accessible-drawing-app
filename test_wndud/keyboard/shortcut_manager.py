# shortcut_manager.py

# 현재 유지 중인 modifier
active_modifier = None
current_hover_key = None

# modifier 키 목록
MODIFIER_KEYS = {
    "LCtrl",
    "RCtrl",
    "LShift",
    "RShift",
    "LAlt",
    "RAlt"
}
CTRL_ALLOWED_KEYS = {
    "C",
    "V",
    "A",
    "Z",
    "Y",
    "F",
    "Shift"
}

SHIFT_ALLOWED_KEYS = {
    "A",
    "B",
    "C"
}

ALT_ALLOWED_KEYS = {
    "Tab",
    "F4"
}

# 중복 입력 방지
last_key = None


def normalize_key(key):

    if key in ["LCtrl", "RCtrl"]:
        return "Ctrl"

    if key in ["LShift", "RShift"]:
        return "Shift"

    if key in ["LAlt", "RAlt"]:
        return "Alt"

    return key


def process_key(detected_key):

    global active_modifier
    global last_key
    global current_hover_key

    if detected_key is None:
        return

    # =========================
    # 같은 키 계속 누르고 있으면 무시
    # =========================
    if detected_key == current_hover_key:
        return

    current_hover_key = detected_key

    # =========================
    # modifier 키면 저장만
    # =========================
    if detected_key in MODIFIER_KEYS:

        active_modifier = normalize_key(detected_key)

        print(f"[MOD SET] {active_modifier}")

        return

    # =========================
    # modifier 조합 실행
    # =========================
    if active_modifier is not None:

        allowed_keys = get_allowed_keys(active_modifier)

    # 허용 키인 경우
    if detected_key in allowed_keys:

        print(f"[SHORTCUT] {active_modifier} + {detected_key}")

        # Ctrl 유지
        return

    # 허용 안된 키면 modifier 해제
    else:

        print(f"[MOD RELEASE] {active_modifier}")

        active_modifier = None

        # 일반 키 처리
        print(f"[KEY] {detected_key}")

        return

def reset_key_state():

    global current_hover_key

    current_hover_key = None

def get_allowed_keys(modifier):

    if modifier == "Ctrl":
        return CTRL_ALLOWED_KEYS

    if modifier == "Shift":
        return SHIFT_ALLOWED_KEYS

    if modifier == "Alt":
        return ALT_ALLOWED_KEYS

    return set()