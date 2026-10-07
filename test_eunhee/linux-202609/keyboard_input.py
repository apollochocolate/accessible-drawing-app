import ctypes
import shutil
import subprocess
import sys
from pynput.keyboard import Controller, Key

keyboard = Controller()

# 다음 한 번의 문자 입력에 적용되는 Shift 상태
shift_mode = False
caps_mode = False


# ==========================
# 한/영 전환 (OS별 구현)
# ==========================
VK_HANGUL = 0x15
KEYEVENTF_KEYUP = 0x0002

# ibus는 fcitx5와 달리 별도의 "토글" 명령이 없어 현재 엔진을 조회한 뒤
# 아래 두 엔진 이름 사이를 직접 전환합니다. 환경에 따라 실제 엔진 이름이
# 다를 수 있으니 `ibus engine`으로 현재 값을 확인하고 필요하면 수정하세요.
IBUS_HANGUL_ENGINE = "hangul"
IBUS_LATIN_ENGINE = "xkb:us::eng"


def _toggle_hangul_windows():
    user32 = ctypes.windll.user32
    user32.keybd_event(VK_HANGUL, 0, 0, 0)
    user32.keybd_event(VK_HANGUL, 0, KEYEVENTF_KEYUP, 0)


def _toggle_hangul_fcitx5():
    """fcitx5-remote -t 로 활성 입력기 on/off를 토글합니다."""
    if shutil.which("fcitx5-remote") is None:
        return False
    try:
        subprocess.run(
            ["fcitx5-remote", "-t"],
            check=True, timeout=1,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.SubprocessError, OSError):
        return False


def _toggle_hangul_ibus():
    """현재 ibus 엔진을 조회해 한글 엔진과 영문 엔진 사이를 전환합니다."""
    if shutil.which("ibus") is None:
        return False
    try:
        current = subprocess.run(
            ["ibus", "engine"],
            check=True, timeout=1,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        ).stdout.strip().lower()

        target = (
            IBUS_LATIN_ENGINE
            if IBUS_HANGUL_ENGINE in current
            else IBUS_HANGUL_ENGINE
        )

        subprocess.run(
            ["ibus", "engine", target],
            check=True, timeout=1,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True
    except (subprocess.SubprocessError, OSError):
        return False


def toggle_hangul():
    """한/영 전환 키를 실제 키 입력처럼 보냅니다."""
    if sys.platform.startswith("win"):
        _toggle_hangul_windows()
        print("[한/영] 입력 전환")
        return

    if _toggle_hangul_fcitx5():
        print("[한/영] 입력 전환 (fcitx5)")
        return

    if _toggle_hangul_ibus():
        print("[한/영] 입력 전환 (ibus)")
        return

    print("[한/영] fcitx5/ibus를 찾지 못했습니다. IME 설치 상태를 확인하세요.")


# ==========================
# 특수키
# ==========================
SPECIAL = {
    "Space": Key.space,
    "Enter": Key.enter,
    "Backspace": Key.backspace,
    "BkSp": Key.backspace,
    "Tab": Key.tab,
    "Esc": Key.esc,
    "Up": Key.up,
    "Down": Key.down,
    "Left": Key.left,
    "Right": Key.right,
    "Ins": Key.insert,
    "Del": Key.delete,
}


# ==========================
# Function 키
# ==========================
FKEYS = {
    f"F{i}": getattr(Key, f"f{i}")
    for i in range(1, 13)
}


# ==========================
# Modifier
# ==========================
MODIFIER = {
    "Ctrl": Key.ctrl,
    "Shift": Key.shift,
    "Alt": Key.alt,
    "Win": Key.cmd,
}


# ==========================
# 실제 키 1회 입력
# ==========================
def _tap(key_obj):
    keyboard.press(key_obj)
    keyboard.release(key_obj)


# ==========================
# 일반 키 입력
# ==========================
def press_key(key):
    global shift_mode
    global caps_mode

    if key is None:
        return

    # 한/영 전환
    if key.strip() == "한/영":
        toggle_hangul()
        return

    # Shift는 토글 상태로 저장하고 다음 문자 1회에 적용
    if key in ["Shift", "LShift", "RShift"]:
        shift_mode = not shift_mode
        print("[SHIFT]", "ON" if shift_mode else "OFF")
        return

    # Caps Lock도 프로그램 내부 토글 상태로 유지
    if key == "Caps":
        caps_mode = not caps_mode
        print("[CAPS]", "ON" if caps_mode else "OFF")
        return

    # 특수키
    if key in SPECIAL:
        _tap(SPECIAL[key])
        return

    # F1~F12
    if key in FKEYS:
        _tap(FKEYS[key])
        return

    # Fn은 OS 입력으로 일반적으로 전송할 수 없으므로 무시
    if key == "Fn":
        print("[FN] 소프트웨어 입력 미지원")
        return

    # 한자 키는 현재 미구현
    if key.strip() == "한자":
        print("[한자] 현재 미구현")
        return

    # 글자/숫자/기호 1글자 키
    if len(key) == 1:
        # 알파벳은 Caps와 Shift를 XOR로 처리
        # 단, 실제 Shift 키를 함께 보내야 한국어 IME에서도
        # q -> ㅂ, Shift+q -> ㅃ 처럼 동작함.
        use_shift = shift_mode

        if key.isalpha() and caps_mode:
            use_shift = not use_shift

        if use_shift:
            keyboard.press(Key.shift)

        try:
            _tap(key.lower() if key.isalpha() else key)
        finally:
            if use_shift:
                keyboard.release(Key.shift)

        # Shift는 1회 입력 후 자동 해제
        if shift_mode:
            shift_mode = False
            print("[SHIFT] AUTO OFF")
        return

    print(f"[UNKNOWN KEY] {key}")


# ==========================
# 단축키 입력
# ==========================
def press_shortcut(modifier, key):
    if modifier not in MODIFIER:
        return

    modifier_key = MODIFIER[modifier]
    keyboard.press(modifier_key)

    try:
        if key in SPECIAL:
            _tap(SPECIAL[key])
        elif key in FKEYS:
            _tap(FKEYS[key])
        elif len(key) == 1:
            _tap(key.lower() if key.isalpha() else key)
    finally:
        keyboard.release(modifier_key)
