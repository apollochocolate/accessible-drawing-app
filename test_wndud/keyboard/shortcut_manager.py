# shortcut_manager.py

# =========================
# 현재 활성 modifier
# =========================
active_modifier = None

# 현재 hover 중인 키
current_hover_key = None

# =========================
# modifier 키 목록
# =========================
MODIFIER_KEYS = {
    "LCtrl",
    "RCtrl",
    "LShift",
    "RShift",
    "LAlt",
    "RAlt",
    "Mode"
}

# =========================
# modifier별 허용 키
# =========================
CTRL_ALLOWED_KEYS = {
    "C",
    "V",
    "A",
    "Z",
    "Y",
    "F"
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

MODE_ALLOWED_KEYS = {
    "Space"
}


# =========================
# modifier 이름 통일
# =========================
def normalize_key(key):

    if key in ["LCtrl", "RCtrl"]:
        return "Ctrl"

    if key in ["LShift", "RShift"]:
        return "Shift"

    if key in ["LAlt", "RAlt"]:
        return "Alt"

    return key


# =========================
# modifier별 허용 키 반환
# =========================
def get_allowed_keys(modifier):

    if modifier == "Ctrl":
        return CTRL_ALLOWED_KEYS

    if modifier == "Shift":
        return SHIFT_ALLOWED_KEYS

    if modifier == "Alt":
        return ALT_ALLOWED_KEYS

    if modifier == "Mode":
        return MODE_ALLOWED_KEYS

    return set()


# =========================
# 키 처리
# =========================
def process_key(detected_key):

    global active_modifier
    global current_hover_key

    if detected_key is None:
        return

    # =========================
    # 같은 키 반복 방지
    # =========================
    if detected_key == current_hover_key:
        return

    current_hover_key = detected_key

    # =========================
    # modifier 키 입력
    # =========================
    if detected_key in MODIFIER_KEYS:

        active_modifier = normalize_key(detected_key)

        print(f"[MOD SET] {active_modifier}")

        return

    # =========================
    # modifier 상태일 때
    # =========================
    if active_modifier is not None:

        allowed_keys = get_allowed_keys(active_modifier)

        # 허용 키인 경우
        if detected_key in allowed_keys:

            print(f"[SHORTCUT] {active_modifier} + {detected_key}")

            # shortcut 실행 후 modifier 해제
            active_modifier = None

            return

        # 허용 안된 키면 무시
        else:

            print(f"[IGNORED] {detected_key}")

            # modifier 유지
            return

    # =========================
    # 일반 키 처리
    # =========================
    print(f"[KEY] {detected_key}")


# =========================
# 레이저 뗐을 때 초기화
# =========================
def reset_key_state():

    global current_hover_key

    current_hover_key = None