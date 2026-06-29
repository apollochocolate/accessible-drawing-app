# shortcut_manager.py

import time
from keyboard_input import press_key, press_shortcut

# =========================
# 현재 활성 modifier
# =========================
active_modifier = None

# 현재 레이저가 가리키는 키
hover_key = None

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

    if key == "Ctrl":
        return "Ctrl"

    if key in ["LShift", "RShift"]:
        return "Shift"

    if key == "Alt":
        return "Alt"

    if key == "Win":
        return "Win"

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


# ======================================================
# 레이저가 현재 어떤 키를 가리키는지만 저장
# (입력하지 않음!!)
# ======================================================
def process_key(detected_key):

    global hover_key

    hover_key = detected_key


# ======================================================
# 얼굴인식에서 좌클릭 신호가 들어오면 호출
# ======================================================
def click_current_key():

    global hover_key

    if hover_key is None:
        return

    process_click(hover_key)


# ======================================================
# 실제 입력 처리
# ======================================================
def process_click(detected_key):

    global active_modifier
    global modifier_start_time

    check_modifier_timeout()

    if detected_key is None:
        return

    # -----------------------------
    # modifier 선택
    # -----------------------------
    if detected_key in MODIFIER_KEYS:

        new_modifier = normalize_key(detected_key)

        if active_modifier != new_modifier:
            print(f"[MOD SET] {new_modifier}")

        active_modifier = new_modifier
        modifier_start_time = time.time()

        return

    # -----------------------------
    # modifier 적용
    # -----------------------------
    if active_modifier is not None:

        allowed = get_allowed_keys(active_modifier)

        if detected_key in allowed:

            print(f"[SHORTCUT] {active_modifier} + {detected_key}")

            press_shortcut(active_modifier, detected_key)

            clear_modifier()

        else:
            print(f"[WAIT] {active_modifier} 유지")

        return

    # -----------------------------
    # 일반 키 입력
    # -----------------------------
    print(f"[KEY] {detected_key}")

    press_key(detected_key)

    global hover_key
    hover_key = None


# ======================================================
# 현재 레이저가 가리키는 키 반환 (선택사항)
# ======================================================
def get_hover_key():

    return hover_key


# ======================================================
# 레이저가 키에서 벗어났을 때
# ======================================================
def reset_key_state():

    global hover_key

    hover_key = None