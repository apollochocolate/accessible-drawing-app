"""음성 버튼으로 켜고 끌 수 있는 STT 모듈.

음성 버튼을 얼굴 클릭하면 main.py에서 VoiceController.toggle()을 호출합니다.
켜진 뒤에는 아래 명령을 말할 수 있습니다.

- 클릭 / 좌클릭
- 우클릭
- 더블클릭
- 스크롤 위 / 위로
- 스크롤 아래 / 아래로
- 음성 종료 / 음성 끄기 / 음성 중지
"""

import threading
import time

import pyautogui

try:
    import speech_recognition as sr
except Exception:
    sr = None


LANGUAGE = "ko-KR"
ENERGY_THRESHOLD = 300
PAUSE_THRESHOLD = 0.6
LISTEN_TIMEOUT = 1
PHRASE_TIME_LIMIT = 3

# 길고 구체적인 명령을 먼저 검사해야 합니다.
COMMAND_ACTIONS = [
    ("스크롤 위", "scroll_up"),
    ("위로", "scroll_up"),
    ("올려", "scroll_up"),
    ("스크롤 아래", "scroll_down"),
    ("아래로", "scroll_down"),
    ("내려", "scroll_down"),
    ("더블클릭", "left_double"),
    ("더블 클릭", "left_double"),
    ("우클릭", "right_single"),
    ("오른쪽 클릭", "right_single"),
    ("좌클릭", "left_single"),
    ("왼쪽 클릭", "left_single"),
    ("클릭", "left_single"),
]

STOP_COMMANDS = ("음성 종료", "음성 끄기", "음성 중지", "그만", "종료")


class VoiceController:
    """STT 스레드의 시작·중지와 명령 전달을 관리합니다."""

    def __init__(self, action_callback):
        self.action_callback = action_callback
        self.stop_event = threading.Event()
        self.thread = None
        self.last_message = "VOICE: OFF"

    @property
    def is_running(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self):
        if sr is None:
            self.last_message = "VOICE: SpeechRecognition 없음"
            print("[음성 오류] SpeechRecognition 패키지가 설치되어 있지 않습니다.")
            print("설치 명령어: python -m pip install SpeechRecognition PyAudio")
            return False

        if self.is_running:
            self.last_message = "VOICE: ON"
            return False

        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="VoiceSTT",
        )
        self.thread.start()
        self.last_message = "VOICE: STARTING"
        return True

    def stop(self):
        if not self.is_running:
            self.last_message = "VOICE: OFF"
            return False

        self.stop_event.set()
        self.last_message = "VOICE: STOPPING"
        return True

    def toggle(self):
        if self.is_running:
            print("[음성] 버튼 입력: 음성 제어 OFF")
            return self.stop()

        print("[음성] 버튼 입력: 음성 제어 ON")
        return self.start()

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
                print("[음성] 활성화됨")
                print("[음성] 명령어: 클릭 / 우클릭 / 더블클릭 / 스크롤 위 / 스크롤 아래 / 음성 종료")

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

                    matched = False
                    for keyword, action_id in COMMAND_ACTIONS:
                        if keyword in text:
                            print(f"[음성 명령] {keyword} -> {action_id}")
                            threading.Thread(
                                target=self._run_action,
                                args=(action_id,),
                                daemon=True,
                            ).start()
                            matched = True
                            break

                    if not matched:
                        print(f"[음성] 매핑된 명령이 없습니다: {text}")

        except OSError as exc:
            print(f"[음성 오류] 마이크를 열 수 없습니다: {exc}")
            self.last_message = "VOICE: MIC ERROR"
        except AttributeError as exc:
            print(f"[음성 오류] PyAudio가 설치되어 있지 않을 수 있습니다: {exc}")
            print("설치 명령어: python -m pip install PyAudio")
            self.last_message = "VOICE: PYAUDIO ERROR"
        except Exception as exc:
            print(f"[음성 오류] STT가 중단되었습니다: {exc}")
            self.last_message = "VOICE: ERROR"
        finally:
            if "ERROR" not in self.last_message and "없음" not in self.last_message:
                self.last_message = "VOICE: OFF"
            print("[음성] 음성 제어가 종료되었습니다.")


# 이 파일만 단독 실행할 때 테스트할 수 있습니다.
def _standalone_action(action_id):
    if action_id == "left_single":
        pyautogui.click(button="left")
    elif action_id == "right_single":
        pyautogui.click(button="right")
    elif action_id == "left_double":
        pyautogui.doubleClick(button="left")
    elif action_id == "scroll_up":
        pyautogui.scroll(5)
    elif action_id == "scroll_down":
        pyautogui.scroll(-5)


if __name__ == "__main__":
    voice = VoiceController(_standalone_action)
    voice.start()
    try:
        while voice.is_running:
            time.sleep(0.2)
    except KeyboardInterrupt:
        voice.stop()
