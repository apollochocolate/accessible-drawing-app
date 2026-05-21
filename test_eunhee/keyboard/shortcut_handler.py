"""
shortcut_handler.py
───────────────────────────────────────────────
keyboard-mapping.py 를 직접 수정하지 않고,
해당 파일의 함수/변수만 빌려와서 조합키(단축키) 로직을 처리하는 모듈.

플로우차트 요약
  [수식키(Win/Ctrl/Shift/Alt) 감지] → 유지(hold)
    → 다음 키가 다른 수식키인지 확인
        YES → 계속 유지 → 앞의 수식키들 제외한 키 감지 → 단축어 수행
        NO  → 바로 단축어 수행
"""

import sys
import os
import time
import importlib
import types

# ─────────────────────────────────────────────
# keyboard-mapping.py 에서 필요한 것만 꺼내오기
# (실행 코드가 모듈 레벨에 있으므로 통째 import하면
#  cv2 창이 열려버림 → 필요한 심볼만 골라서 가져옴)
# ─────────────────────────────────────────────
def _load_kb_symbols():
    """
    keyboard-mapping.py 를 exec 로 읽어서
    KEY_MAP / detect_red_laser / get_key_at /
    draw_keyboard_overlay / put_text_pil /
    FONT_MD / WIN_W / WIN_H / TUNE_WIN 등을 반환.

    cv2 창 생성·VideoCapture·메인 루프는 실행되지 않도록
    해당 심볼들은 stub 으로 교체한 뒤 실행.
    """
    kb_path = os.path.join(os.path.dirname(__file__), "keyboard-mapping.py")

    # ── cv2 stub: 창 생성 / VideoCapture / imshow 등만 무력화 ──
    import cv2 as _cv2
    import numpy as _np

    class _CV2Stub(types.ModuleType):
        """namedWindow / createTrackbar / VideoCapture / imshow 만 막는 stub"""
        def __getattr__(self, name):
            # 막아야 할 함수들
            _noop = {"namedWindow","resizeWindow","createTrackbar",
                     "VideoCapture","imshow","waitKey","destroyAllWindows",
                     "destroyWindow"}
            if name in _noop:
                return lambda *a, **kw: None
            return getattr(_cv2, name)

    stub = _CV2Stub("cv2")
    # VideoCapture 는 객체를 반환해야 하므로 별도 처리
    class _FakeCap:
        def read(self): return False, _np.zeros((480,640,3), dtype=_np.uint8)
        def set(self, *a): pass
        def release(self): pass
    stub.VideoCapture = lambda *a: _FakeCap()
    stub.getTrackbarPos = lambda *a: 0  # 트랙바 값은 0으로 고정

    # keyboard-mapping.py 소스를 읽어서 별도 네임스페이스에서 실행
    with open(kb_path, encoding="utf-8") as f:
        src = f.read()

    ns = {
        "__name__": "__kb_mapping__",
        "cv2": stub,          # stub 주입
    }
    exec(compile(src, kb_path, "exec"), ns)

    return ns   # KEY_MAP, detect_red_laser, get_key_at, ... 전부 포함


_KB = _load_kb_symbols()

# 필요한 심볼 꺼내기
KEY_MAP            = _KB["KEY_MAP"]
detect_red_laser   = _KB["detect_red_laser"]
get_key_at         = _KB["get_key_at"]
draw_keyboard_overlay = _KB["draw_keyboard_overlay"]
put_text_pil       = _KB["put_text_pil"]
FONT_MD            = _KB["FONT_MD"]
WIN_W              = _KB["WIN_W"]
WIN_H              = _KB["WIN_H"]

# ─────────────────────────────────────────────
# 수식키 정의 (플로우차트의 "유지" 대상 키들)
# ─────────────────────────────────────────────
MODIFIER_KEYS = {"LCtrl", "RCtrl", "LShift", "RShift", "LAlt", "RAlt", "Win"}

# 내부 이름 → 표시 이름
MODIFIER_LABEL = {
    "LCtrl":  "Ctrl",  "RCtrl":  "Ctrl",
    "LShift": "Shift", "RShift": "Shift",
    "LAlt":   "Alt",   "RAlt":   "Alt",
    "Win":    "Win",
}


# ─────────────────────────────────────────────
# 단축키 액션 테이블
# ─────────────────────────────────────────────
# key : frozenset(수식키 표시명) + 일반키 이름  →  (설명, 실행함수)
# 예) Ctrl+C  →  frozenset({"Ctrl"}) | {"C"}
#
# 등록 형식: SHORTCUT_TABLE[ (frozenset(수식명), 일반키) ] = (설명, callable)
# ─────────────────────────────────────────────

def _action_copy():
    print("📋 [단축어 수행] Ctrl+C → 복사(Copy)")

def _action_paste():
    print("📋 [단축어 수행] Ctrl+V → 붙여넣기(Paste)")

def _action_cut():
    print("✂️  [단축어 수행] Ctrl+X → 잘라내기(Cut)")

def _action_undo():
    print("↩️  [단축어 수행] Ctrl+Z → 실행 취소(Undo)")

def _action_select_all():
    print("🔲 [단축어 수행] Ctrl+A → 전체 선택(Select All)")

SHORTCUT_TABLE = {
    (frozenset({"Ctrl"}), "C"): ("복사",       _action_copy),
    (frozenset({"Ctrl"}), "V"): ("붙여넣기",   _action_paste),
    (frozenset({"Ctrl"}), "X"): ("잘라내기",   _action_cut),
    (frozenset({"Ctrl"}), "Z"): ("실행취소",   _action_undo),
    (frozenset({"Ctrl"}), "A"): ("전체선택",   _action_select_all),
}


# ─────────────────────────────────────────────
# ShortcutDetector : 플로우차트 로직 구현
# ─────────────────────────────────────────────
class ShortcutDetector:
    """
    매 프레임마다 feed(detected_key) 를 호출하면
    플로우차트에 따라 조합키를 감지하고 단축어를 수행.

    상태 머신:
        IDLE      → 수식키 감지 시 HOLDING 으로 전환
        HOLDING   → 추가 수식키면 계속 HOLDING
                    일반키면 단축어 실행 후 IDLE 복귀
                    일정 시간(hold_timeout) 안에 일반키 없으면 IDLE 복귀
    """

    HOLD_TIMEOUT = 3.0   # 초 — 수식키를 누른 채 이 시간 안에 일반키 안 오면 취소

    def __init__(self):
        self.held_modifiers: set[str] = set()   # 현재 유지 중인 수식키 표시명
        self.state = "IDLE"
        self._hold_start = 0.0
        self._prev_key   = None   # 직전 프레임 키 (중복 트리거 방지)

    # ── 외부에서 매 프레임 호출 ──────────────────
    def feed(self, detected_key: str | None) -> str | None:
        """
        detected_key : 현재 프레임의 레이저 감지 키 (없으면 None)
        반환값       : 수행된 단축어 설명 문자열, 없으면 None
        """
        # 같은 키가 연속으로 들어오면 무시 (한 번 눌림으로 처리)
        if detected_key == self._prev_key:
            # 수식키는 계속 홀드 상태 유지
            if self.state == "HOLDING" and time.time() - self._hold_start > self.HOLD_TIMEOUT:
                self._reset()
                print("⏱️  [타임아웃] 수식키 홀드 취소")
            return None
        self._prev_key = detected_key

        if detected_key is None:
            return None

        # ── IDLE 상태 ────────────────────────────
        if self.state == "IDLE":
            if detected_key in MODIFIER_KEYS:
                label = MODIFIER_LABEL[detected_key]
                self.held_modifiers.add(label)
                self.state = "HOLDING"
                self._hold_start = time.time()
                print(f"🔒 [유지] {self._mod_str()} 홀드 시작")
            else:
                # 수식키 없이 일반키 → 단순 입력 (단축어 없음)
                pass
            return None

        # ── HOLDING 상태 ────────────────────────
        if self.state == "HOLDING":
            # 타임아웃 체크
            if time.time() - self._hold_start > self.HOLD_TIMEOUT:
                self._reset()
                print("⏱️  [타임아웃] 수식키 홀드 취소")
                return None

            if detected_key in MODIFIER_KEYS:
                # 추가 수식키 → 계속 유지 (YES 분기)
                label = MODIFIER_LABEL[detected_key]
                if label not in self.held_modifiers:
                    self.held_modifiers.add(label)
                    print(f"🔒 [유지 추가] {self._mod_str()}")
                return None
            else:
                # 일반키 감지 → 단축어 실행 (NO 또는 YES→앞3개제외 분기)
                result = self._try_shortcut(detected_key)
                self._reset()
                return result

        return None

    # ── 단축어 조회 및 실행 ──────────────────────
    def _try_shortcut(self, key: str) -> str | None:
        lookup = (frozenset(self.held_modifiers), key.upper())
        if lookup in SHORTCUT_TABLE:
            desc, action = SHORTCUT_TABLE[lookup]
            combo = "+".join(sorted(self.held_modifiers)) + "+" + key.upper()
            print(f"⚡ [단축어 수행] {combo} → {desc}")
            action()
            return desc
        else:
            combo = "+".join(sorted(self.held_modifiers)) + "+" + key.upper()
            print(f"❓ [미등록 단축키] {combo}")
            return None

    def _mod_str(self) -> str:
        return "+".join(sorted(self.held_modifiers)) if self.held_modifiers else "(없음)"

    def _reset(self):
        self.held_modifiers.clear()
        self.state = "IDLE"
        self._hold_start = 0.0

    # ── 현재 상태 요약 (오버레이 표시용) ────────
    def status_text(self) -> str:
        if self.state == "HOLDING":
            return f"HOLD: {self._mod_str()}"
        return ""


# ─────────────────────────────────────────────
# 메인 루프 (이 파일을 직접 실행할 때만 동작)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import cv2
    import numpy as np

    TUNE_WIN = "[ HSV Tuning ] - q:quit  m:mask on/off"
    cv2.namedWindow(TUNE_WIN)
    cv2.resizeWindow(TUNE_WIN, 600, 350)

    cv2.createTrackbar("H_low1",  TUNE_WIN, 0,   10,  lambda x: None)
    cv2.createTrackbar("H_high1", TUNE_WIN, 10,  30,  lambda x: None)
    cv2.createTrackbar("H_low2",  TUNE_WIN, 160, 180, lambda x: None)
    cv2.createTrackbar("H_high2", TUNE_WIN, 180, 180, lambda x: None)
    cv2.createTrackbar("S_min",   TUNE_WIN, 80,  255, lambda x: None)
    cv2.createTrackbar("V_min",   TUNE_WIN, 100, 255, lambda x: None)
    cv2.createTrackbar("Blur",    TUNE_WIN, 5,   21,  lambda x: None)
    cv2.createTrackbar("Area",    TUNE_WIN, 5,   200, lambda x: None)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  WIN_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WIN_H)

    detector  = ShortcutDetector()
    show_mask = False

    print("실행 중... q:종료 / m:마스크 창 on/off")
    print("테스트: LCtrl 레이저 → C 레이저 → Ctrl+C 단축키 실행")

    while True:
        ret, frame = cap.read()
        if not ret:
            frame = np.zeros((WIN_H, WIN_W, 3), dtype=np.uint8)

        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (WIN_W, WIN_H))

        h_lo   = cv2.getTrackbarPos("H_low1",  TUNE_WIN)
        h_hi   = cv2.getTrackbarPos("H_high1", TUNE_WIN)
        h_lo2  = cv2.getTrackbarPos("H_low2",  TUNE_WIN)
        h_hi2  = cv2.getTrackbarPos("H_high2", TUNE_WIN)
        s_min  = cv2.getTrackbarPos("S_min",   TUNE_WIN)
        v_min  = cv2.getTrackbarPos("V_min",   TUNE_WIN)
        blur_k = max(cv2.getTrackbarPos("Blur", TUNE_WIN), 1)
        area_m = cv2.getTrackbarPos("Area",    TUNE_WIN)

        cx, cy, mask = detect_red_laser(
            frame, h_lo, h_hi, h_lo2, h_hi2, s_min, v_min, blur_k, area_m
        )
        detected_key = None

        if cx is not None:
            detected_key = get_key_at(cx, cy)
            cv2.circle(frame, (cx, cy), 8,  (0, 0, 255), -1)
            cv2.circle(frame, (cx, cy), 12, (255, 255, 255), 2)

        # ── 조합키 감지 (핵심 호출) ──────────────
        result = detector.feed(detected_key)

        draw_keyboard_overlay(frame, detected_key)

        # 상태 표시 (좌하단)
        hold_text = detector.status_text()
        status = hold_text if hold_text else (f"Key: {detected_key}" if detected_key else "Key: ---")
        color  = (0, 200, 255) if hold_text else (0, 255, 180)
        cv2.rectangle(frame, (0, WIN_H - 32), (260, WIN_H), (0, 0, 0), -1)
        put_text_pil(frame, status, 130, WIN_H - 16, FONT_MD, color)

        # 단축키 수행 결과 표시 (화면 중앙 상단, 1.5초)
        if result:
            put_text_pil(frame, f"⚡ {result}", WIN_W // 2, 30, FONT_MD, (0, 255, 100))

        # 레이저 감지 여부 (우상단)
        dot_color = (0, 255, 0) if cx is not None else (0, 0, 255)
        dot_label = "LASER ON" if cx is not None else "NO LASER"
        cv2.circle(frame, (WIN_W - 90, 18), 8, dot_color, -1)
        cv2.putText(frame, dot_label, (WIN_W - 78, 23),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, dot_color, 1, cv2.LINE_AA)

        cv2.imshow("Laser Keyboard + Shortcut", frame)

        if show_mask:
            cv2.imshow("Mask Debug", mask)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("m"):
            show_mask = not show_mask
            if not show_mask:
                cv2.destroyWindow("Mask Debug")

    cap.release()
    cv2.destroyAllWindows()
