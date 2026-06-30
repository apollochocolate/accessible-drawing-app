# shortcut_manager.py

import time

# =========================
# 현재 활성 modifier
# =========================
active_modifier = None

# 현재 hover 중 키
current_hover_key = None

# modifier 시작 시간
modifier_start_time = None

# modifier 유지 시간
MODIFIER_TIMEOUT = 5


# =========================
# modifier 키 목록
# =========================
MODIFIER_KEYS = {
    "Ctrl",
    "LShift",
    "RShift",
    "Alt",
    "Win"
}


# =========================
# modifier별 허용 키
# =========================
CTRL_ALLOWED_KEYS = {
    "C",
    "V",
    "A",
    "Z",
    "F",
    "S"
}

SHIFT_ALLOWED_KEYS = {
    "Up",
    "Down",
    "Left",
    "Right"
}

ALT_ALLOWED_KEYS = {
    "Tab"
}

WIN_ALLOWED_KEYS = {
    "Up",
    "Down",
    "Left",
    "Right"
}


# =========================
# modifier 이름 통일
# =========================
def normalize_key(key):

    if key in ["Ctrl"]:
        return "Ctrl"

    if key in ["LShift", "RShift"]:
        return "Shift"

    if key in ["Alt"]:
        return "Alt"

    return key


# =========================
# 허용 키 반환
# =========================
def get_allowed_keys(modifier):

    if modifier == "Ctrl":
        return CTRL_ALLOWED_KEYS

    if modifier == "Shift":
        return SHIFT_ALLOWED_KEYS

    if modifier == "Alt":
        return ALT_ALLOWED_KEYS

    if modifier == "Win":
        return WIN_ALLOWED_KEYS

    return set()


# =========================
# 현재 modifier 반환
# =========================
def get_active_modifier():
    return active_modifier


# =========================
# modifier 해제
# =========================
def clear_modifier():

    global active_modifier
    global modifier_start_time

    if active_modifier is not None:
        print(f"[MOD CLEAR] {active_modifier}")

    active_modifier = None
    modifier_start_time = None


# =========================
# timeout 체크
# =========================
def check_modifier_timeout():

    global active_modifier
    global modifier_start_time

    if active_modifier is None:
        return

    if modifier_start_time is None:
        return

    elapsed = time.time() - modifier_start_time

    if elapsed >= MODIFIER_TIMEOUT:

        print("[TIMEOUT] modifier 해제")

        clear_modifier()


# =========================
# 키 처리
# =========================
def process_key(detected_key):

    global active_modifier
    global current_hover_key
    global modifier_start_time

    if detected_key is None:
        return

    # =========================
    # timeout 체크
    # =========================
    check_modifier_timeout()

    # =========================
    # 같은 키 반복 방지
    # =========================
    if detected_key == current_hover_key:
        return

    current_hover_key = detected_key

    # =========================
    # modifier 키 선택
    # =========================
    if detected_key in MODIFIER_KEYS:

        new_modifier = normalize_key(detected_key)

        # modifier 변경 가능
        if active_modifier != new_modifier:

            if active_modifier is not None:

                print(
                    f"[MOD CHANGE] "
                    f"{active_modifier} -> {new_modifier}"
                )

            active_modifier = new_modifier

            modifier_start_time = time.time()

            print(f"[MOD SET] {active_modifier}")

        return

    # =========================
    # modifier 유지 상태
    # =========================
    if active_modifier is not None:

        # 허용 키 목록
        allowed_keys = get_allowed_keys(active_modifier)

        # 허용 키
        if detected_key in allowed_keys:

            print(
                f"[SHORTCUT] "
                f"{active_modifier} + {detected_key}"
            )

            clear_modifier()

            return

        # 허용 안 된 키
        else:

            # modifier 유지
            return

    # =========================
    # 일반 키
    # =========================
    print(f"[KEY] {detected_key}")


# =========================
# 레이저 뗐을 때
# =========================
def reset_key_state():

    global current_hover_key

    current_hover_key = None