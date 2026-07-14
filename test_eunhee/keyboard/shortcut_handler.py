"""
shortcut_handler.py
───────────────────────────────────────────────────────────────
keyboard-mapping.py 를 직접 수정하지 않고,
필요한 함수/변수만 가져와서 조합키(단축키) 로직을 처리하는 모듈.

동작 규칙
  - 수식키 유지 조건 : 레이저가 수식키 위에 계속 올려져 있어야 유지
  - 수식키 해제 조건 : 레이저가 수식키 영역을 벗어나는 순간 즉시 해제
  - 단축키 수행 후   : 즉시 IDLE 복귀
  - 타임아웃         : 마지막 수식키 감지로부터 HOLD_TIMEOUT 초 경과 시 IDLE 복귀
"""

import os
import time
import types

import cv2
import numpy as np


# ════════════════════════════════════════════════════════════════
# keyboard-mapping.py 에서 필요한 심볼만 안전하게 로드
# (모듈 레벨 실행 코드가 있으므로 cv2 창 관련 함수를 stub으로 교체)
# ════════════════════════════════════════════════════════════════

def _load_kb_symbols():
    kb_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keyboard-mapping.py")

    # ── cv2 stub: 창 생성 / 트랙바 / 캡처 / 표시 함수만 무력화 ──
    class _CV2Stub(types.ModuleType):
        _NOOP = {
            "namedWindow", "resizeWindow", "createTrackbar",
            "imshow", "waitKey", "destroyAllWindows", "destroyWindow",
        }
        def __getattr__(self, name):
            if name in self._NOOP:
                return lambda *a, **kw: None
            return getattr(cv2, name)

    stub = _CV2Stub("cv2")

    class _FakeCap:
        def read(self):    return False, np.zeros((480, 640, 3), dtype=np.uint8)
        def set(self, *a): pass
        def release(self): pass

    stub.VideoCapture    = lambda *a: _FakeCap()
    stub.getTrackbarPos  = lambda *a: 0

    with open(kb_path, encoding="utf-8") as f:
        src = f.read()

    ns = {"__name__": "__kb_mapping__", "cv2": stub}
    exec(compile(src, kb_path, "exec"), ns)
    return ns


_KB = _load_kb_symbols()

# 필요한 심볼 꺼내기
KEY_MAP               = _KB["KEY_MAP"]
detect_red_laser      = _KB["detect_red_laser"]
get_key_at            = _KB["get_key_at"]
draw_keyboard_overlay = _KB["draw_keyboard_overlay"]
put_text_pil          = _KB["put_text_pil"]
FONT_MD               = _KB["FONT_MD"]
FONT_LG               = _KB["FONT_LG"]
WIN_W                 = _KB["WIN_W"]
WIN_H                 = _KB["WIN_H"]


# ════════════════════════════════════════════════════════════════
# 수식키 정의
# ════════════════════════════════════════════════════════════════

# KEY_MAP 상의 키 이름 → 표시 라벨
MODIFIER_KEYS = {
    "LShift": "Shift", "RShift": "Shift",
    "LCtrl":  "Ctrl",  "RCtrl":  "Ctrl",
    "LAlt":   "Alt",   "RAlt":   "Alt",
    "Win":    "Win",
}


# ════════════════════════════════════════════════════════════════
# 단축키 액션 테이블
#   key : (frozenset(수식키 라벨), 일반키 대문자)
#   val : (설명 문자열, callable)
# ════════════════════════════════════════════════════════════════

def _act_shift_z():
    print("✅ [수행] Shift+Z")

def _act_copy():
    print("📋 [수행] Ctrl+C → 복사")

def _act_paste():
    print("📋 [수행] Ctrl+V → 붙여넣기")

def _act_cut():
    print("✂️  [수행] Ctrl+X → 잘라내기")

def _act_undo():
    print("↩️  [수행] Ctrl+Z → 실행 취소")

def _act_select_all():
    print("🔲 [수행] Ctrl+A → 전체 선택")


SHORTCUT_TABLE: dict = {
    # ── 테스트용 ──────────────────────────────────
    (frozenset({"Shift"}), "Z"): ("Shift+Z", _act_shift_z),

    # ── Ctrl 조합 ─────────────────────────────────
    (frozenset({"Ctrl"}),  "C"): ("Ctrl+C 복사",     _act_copy),
    (frozenset({"Ctrl"}),  "V"): ("Ctrl+V 붙여넣기", _act_paste),
    (frozenset({"Ctrl"}),  "X"): ("Ctrl+X 잘라내기", _act_cut),
    (frozenset({"Ctrl"}),  "Z"): ("Ctrl+Z 실행취소", _act_undo),
    (frozenset({"Ctrl"}),  "A"): ("Ctrl+A 전체선택", _act_select_all),
}


# ════════════════════════════════════════════════════════════════
# ShortcutDetector  —  상태 머신
# ════════════════════════════════════════════════════════════════

class ShortcutDetector:
    """
    상태
      IDLE    : 수식키 감지 없음
      HOLDING : 수식키가 현재 레이저로 눌려 있는 상태

    매 프레임 feed(detected_key) 호출 → 단축키 수행 시 설명 문자열 반환
    """

    HOLD_TIMEOUT = 3.0   # 초 — 수식키 마지막 감지 후 이 시간 지나면 IDLE

    def __init__(self):
        self._state         = "IDLE"
        self._held_mods     = set()    # 현재 유지 중인 수식 라벨
        self._last_mod_time = 0.0      # 마지막으로 수식키 감지한 시각
        self._last_result   = None     # 직전 수행 결과 (화면 표시용)
        self._result_time   = 0.0      # 결과 표시 시작 시각

    # ── 외부에서 매 프레임 호출 ─────────────────────────────────
    def feed(self, detected_key):
        """
        detected_key : 현재 프레임의 레이저 감지 키 (없으면 None)
        반환값       : 이번 프레임에 수행된 단축키 설명, 없으면 None
        """
        now = time.time()

        # ── HOLDING 중 타임아웃 체크 ────────────────────────────
        if self._state == "HOLDING":
            if now - self._last_mod_time > self.HOLD_TIMEOUT:
                print(f"⏱️  [타임아웃] {self._mod_str()} 해제 → IDLE")
                self._reset()
                return None

        # ── detected_key 분류 ────────────────────────────────────
        mod_label = MODIFIER_KEYS.get(detected_key)   # 수식키면 라벨, 아니면 None

        # ① 레이저 없음 ─────────────────────────────────────────
        if detected_key is None:
            if self._state == "HOLDING":
                print(f"🔓 [해제] 레이저 없음 → {self._mod_str()} 해제 → IDLE")
                self._reset()
            return None

        # ② 수식키 감지 ─────────────────────────────────────────
        if mod_label is not None:
            if self._state == "IDLE":
                self._held_mods.add(mod_label)
                self._state = "HOLDING"
                self._last_mod_time = now
                print(f"🔒 [HOLDING 시작] {self._mod_str()}")
            else:
                # HOLDING 중 — 추가 수식키 or 같은 수식키 유지
                if mod_label not in self._held_mods:
                    self._held_mods.add(mod_label)
                    print(f"🔒 [HOLDING 추가] {self._mod_str()}")
                # 수식키가 감지되는 동안 타임아웃 리셋
                self._last_mod_time = now
            return None

        # ③ 일반키 감지 ─────────────────────────────────────────
        if self._state == "IDLE":
            # 수식키 없이 일반키 → 단순 입력, 무시
            return None

        # HOLDING 상태에서 일반키 → 단축키 조회 후 수행 → IDLE
        result = self._execute(detected_key)
        self._reset()
        return result

    # ── 단축키 조회 및 실행 ────────────────────────────────────
    def _execute(self, key):
        lookup = (frozenset(self._held_mods), key.upper())
        combo  = "+".join(sorted(self._held_mods)) + "+" + key.upper()

        if lookup in SHORTCUT_TABLE:
            desc, action = SHORTCUT_TABLE[lookup]
            print(f"⚡ [단축키 수행] {combo} → {desc}")
            action()
            self._last_result = combo
            self._result_time = time.time()
            return desc
        else:
            print(f"❓ [미등록] {combo}")
            return None

    # ── 상태 초기화 ───────────────────────────────────────────
    def _reset(self):
        self._held_mods.clear()
        self._state         = "IDLE"
        self._last_mod_time = 0.0

    # ── 수식키 라벨 문자열 ────────────────────────────────────
    def _mod_str(self):
        return "+".join(sorted(self._held_mods)) if self._held_mods else "(없음)"

    # ── 오버레이 표시용 텍스트 / 색상 ────────────────────────
    def status_text(self):
        """(표시 문자열, BGR 색상) 반환"""
        if self._state == "HOLDING":
            return f"HOLD: {self._mod_str()}", (0, 220, 255)   # 노랑
        return "", (0, 255, 180)

    def result_text(self):
        """단축키 수행 결과를 1.5초 동안 표시"""
        if self._last_result and time.time() - self._result_time < 1.5:
            return f"⚡ {self._last_result}"
        return None


# ════════════════════════════════════════════════════════════════
# 메인 루프  (python shortcut_handler.py 로 직접 실행할 때만 동작)
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":

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

    print("=" * 50)
    print("실행 중 ...  q: 종료  /  m: 마스크 창 on/off")
    print("테스트: Shift 키에 레이저 올린 채 유지 → Z 로 이동")
    print("=" * 50)

    while True:
        ret, frame = cap.read()
        if not ret:
            frame = np.zeros((WIN_H, WIN_W, 3), dtype=np.uint8)

        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (WIN_W, WIN_H))

        # ── 트랙바 파라미터 읽기 ──────────────────────────────
        h_lo   = cv2.getTrackbarPos("H_low1",  TUNE_WIN)
        h_hi   = cv2.getTrackbarPos("H_high1", TUNE_WIN)
        h_lo2  = cv2.getTrackbarPos("H_low2",  TUNE_WIN)
        h_hi2  = cv2.getTrackbarPos("H_high2", TUNE_WIN)
        s_min  = cv2.getTrackbarPos("S_min",   TUNE_WIN)
        v_min  = cv2.getTrackbarPos("V_min",   TUNE_WIN)
        blur_k = max(cv2.getTrackbarPos("Blur", TUNE_WIN), 1)
        area_m = cv2.getTrackbarPos("Area",    TUNE_WIN)

        # ── 레이저 감지 ───────────────────────────────────────
        cx, cy, mask = detect_red_laser(
            frame, h_lo, h_hi, h_lo2, h_hi2, s_min, v_min, blur_k, area_m
        )
        detected_key = None

        if cx is not None:
            detected_key = get_key_at(cx, cy)
            cv2.circle(frame, (cx, cy), 8,  (0, 0, 255), -1)
            cv2.circle(frame, (cx, cy), 12, (255, 255, 255), 2)

        # ── 조합키 상태머신 (핵심 호출) ──────────────────────
        detector.feed(detected_key)

        # ── 키보드 오버레이 ───────────────────────────────────
        draw_keyboard_overlay(frame, detected_key)

        # ── 좌하단 상태 표시 ──────────────────────────────────
        status_str, status_color = detector.status_text()
        if not status_str:
            status_str   = f"Key: {detected_key}" if detected_key else "Key: ---"
            status_color = (0, 255, 180)

        cv2.rectangle(frame, (0, WIN_H - 32), (280, WIN_H), (0, 0, 0), -1)
        put_text_pil(frame, status_str, 140, WIN_H - 16, FONT_MD, status_color)

        # ── 단축키 수행 결과 표시 (상단 중앙, 1.5초) ──────────
        result_str = detector.result_text()
        if result_str:
            cv2.rectangle(frame, (WIN_W//2 - 110, 4), (WIN_W//2 + 110, 36), (0, 0, 0), -1)
            put_text_pil(frame, result_str, WIN_W // 2, 20, FONT_LG, (80, 255, 120))

        # ── 우상단 레이저 감지 표시 ───────────────────────────
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
            print(f"마스크 창: {'ON' if show_mask else 'OFF'}")

    cap.release()
    cv2.destroyAllWindows()
