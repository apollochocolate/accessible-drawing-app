import speech_recognition as sr
import pyautogui
import threading
import time

# ─────────────────────────────────────────
# 설정
# ─────────────────────────────────────────
LANGUAGE = "ko-KR"          # 한국어 STT
ENERGY_THRESHOLD = 300      # 마이크 감도 (낮을수록 민감)
PAUSE_THRESHOLD = 0.6       # 말이 끊긴 후 인식 종료까지 대기 시간(초)

# 인식할 명령어 → 동작 매핑
COMMANDS = {
    "좌클릭":   lambda: pyautogui.click(button='left'),
    "우클릭":   lambda: pyautogui.click(button='right'),
    "더블클릭": lambda: pyautogui.doubleClick(button='left'),
}

# ─────────────────────────────────────────
# 마우스 동작 실행
# ─────────────────────────────────────────
def execute_command(text: str):
    """인식된 텍스트에서 명령어를 찾아 실행"""
    for keyword, action in COMMANDS.items():
        if keyword in text:
            print(f"[명령 실행] → {keyword}")
            action()
            return
    print(f"[인식됨] '{text}' → 매핑된 명령 없음")

# ─────────────────────────────────────────
# STT 메인 루프
# ─────────────────────────────────────────
def listen_loop():
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = ENERGY_THRESHOLD
    recognizer.pause_threshold = PAUSE_THRESHOLD

    mic = sr.Microphone()

    print("=" * 40)
    print("  음성 마우스 제어 시작")
    print("  말할 수 있는 명령어:")
    for cmd in COMMANDS:
        print(f"    🎙️  '{cmd}'")
    print("  종료: Ctrl+C")
    print("=" * 40)

    with mic as source:
        # 주변 소음에 맞게 감도 자동 보정 (1초)
        print("[준비 중] 주변 소음 보정 중...")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print("[대기 중] 말씀하세요!\n")

        while True:
            try:
                # 음성 입력 캡처 (최대 5초 대기)
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=3)

                # Google STT로 텍스트 변환 (인터넷 필요)
                text = recognizer.recognize_google(audio, language=LANGUAGE)
                print(f"[인식 결과] '{text}'")

                # 명령 실행은 별도 스레드에서 (STT 루프 블로킹 방지)
                threading.Thread(target=execute_command, args=(text,), daemon=True).start()

            except sr.WaitTimeoutError:
                # 5초 안에 음성 없으면 다시 대기
                pass
            except sr.UnknownValueError:
                print("[인식 실패] 음성을 인식하지 못했습니다.")
            except sr.RequestError as e:
                print(f"[STT 오류] Google STT 연결 실패: {e}")
                time.sleep(2)
            except KeyboardInterrupt:
                print("\n[종료] 음성 제어를 종료합니다.")
                break

# ─────────────────────────────────────────
# 실행
# ─────────────────────────────────────────
if __name__ == "__main__":
    listen_loop()
