"""음성 명령을 메인 프로그램에 안전하게 연결하는 STT 모듈."""
import threading
import time

import pyautogui
import speech_recognition as sr

LANGUAGE = "ko-KR"
ENERGY_THRESHOLD = 300
PAUSE_THRESHOLD = 0.6
LISTEN_TIMEOUT = 1       # stop() 요청을 최대 약 1초 안에 확인
PHRASE_TIME_LIMIT = 3

# main.py의 execute_mouse_action()이 사용하는 제스처 ID로 변환한다.
COMMAND_ACTIONS = {
    "더블클릭": "left_double",
    "우클릭": "right_single",
    "좌클릭": "left_single",
    "클릭": "left_single",  # '좌클릭'이라고 말하기 어려운 경우를 위한 보조 명령
}
STOP_COMMANDS = ("음성 종료", "음성 끄기", "음성 중지")


class VoiceController:
    """STT 스레드의 시작·중지와 명령 전달을 관리한다."""

    def __init__(self, action_callback):
        self.action_callback = action_callback
        self.stop_event = threading.Event()
        self.thread = None
        self.last_message = "VOICE: OFF"
        self._lock = threading.Lock()

    @property
    def is_running(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self):
        if self.is_running:
            return False
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._listen_loop, daemon=True, name="VoiceSTT")
        self.thread.start()
        self.last_message = "VOICE: STARTING"
        return True

    def stop(self):
        if not self.is_running:
            self.last_message = "VOICE: OFF"
            return False
        self.stop_event.set()
        # recognize_google() 네트워크 처리 중일 수 있으므로 main 루프를 막지 않는다.
        self.last_message = "VOICE: STOPPING"
        return True

    def toggle(self):
        return self.stop() if self.is_running else self.start()

    def _run_action(self, action_id):
        try:
            self.action_callback(action_id)
        except Exception as exc:
            print(f"[음성 명령 오류] 동작 실행 실패: {exc}")

    def _listen_loop(self):
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = ENERGY_THRESHOLD
        recognizer.pause_threshold = PAUSE_THRESHOLD

        try:
            mic = sr.Microphone()
            with mic as source:
                print("[음성] 주변 소음 보정 중...")
                recognizer.adjust_for_ambient_noise(source, duration=1)
                self.last_message = "VOICE: ON"
                print("[음성] 활성화됨: 좌클릭 / 우클릭 / 더블클릭 / 음성 종료")

                while not self.stop_event.is_set():
                    try:
                        audio = recognizer.listen(
                            source,
                            timeout=LISTEN_TIMEOUT,
                            phrase_time_limit=PHRASE_TIME_LIMIT,
                        )
                    except sr.WaitTimeoutError:
                        continue

                    try:
                        text = recognizer.recognize_google(audio, language=LANGUAGE).strip()
                        print(f"[음성 인식] {text}")
                    except sr.UnknownValueError:
                        print("[음성] 인식하지 못했습니다.")
                        continue
                    except sr.RequestError as exc:
                        print(f"[음성 오류] Google STT 연결 실패: {exc}")
                        self.last_message = "VOICE: NETWORK ERROR"
                        if self.stop_event.wait(2):
                            break
                        self.last_message = "VOICE: ON"
                        continue

                    if any(command in text for command in STOP_COMMANDS):
                        print("[음성] 종료 명령을 받았습니다.")
                        self.stop_event.set()
                        break

                    for keyword, action_id in COMMAND_ACTIONS.items():
                        if keyword in text:
                            print(f"[음성 명령] {keyword} -> {action_id}")
                            threading.Thread(
                                target=self._run_action,
                                args=(action_id,),
                                daemon=True,
                            ).start()
                            break
                    else:
                        print(f"[음성] 매핑된 명령이 없습니다: {text}")

        except OSError as exc:
            print(f"[음성 오류] 마이크를 열 수 없습니다: {exc}")
            self.last_message = "VOICE: MIC ERROR"
        except Exception as exc:
            print(f"[음성 오류] STT가 중단되었습니다: {exc}")
            self.last_message = "VOICE: ERROR"
        finally:
            if not self.last_message.endswith("ERROR"):
                self.last_message = "VOICE: OFF"
            print("[음성] 음성 제어가 종료되었습니다.")


# 이 파일만 단독 실행할 때도 테스트할 수 있다.
def _standalone_action(action_id):
    if action_id == "left_single":
        pyautogui.click(button="left")
    elif action_id == "right_single":
        pyautogui.click(button="right")
    elif action_id == "left_double":
        pyautogui.doubleClick(button="left")


if __name__ == "__main__":
    voice = VoiceController(_standalone_action)
    voice.start()
    try:
        while voice.is_running:
            time.sleep(0.2)
    except KeyboardInterrupt:
        voice.stop()
