
import io, threading, time
import pyautogui
import sounddevice as sd
import soundfile as sf
import speech_recognition as sr

LANGUAGE="ko-KR"
SAMPLE_RATE=16000
RECORD_SECONDS=3

COMMANDS={
    "클릭": lambda: pyautogui.click(button="left"),
    "우클릭": lambda: pyautogui.click(button="right"),
    "더블클릭": lambda: pyautogui.doubleClick(button="left"),
}

recognizer=sr.Recognizer()

def record_audio():
    print("[대기] 말씀하세요...")
    audio=sd.rec(int(RECORD_SECONDS*SAMPLE_RATE),samplerate=SAMPLE_RATE,channels=1,dtype="int16")
    sd.wait()
    buf=io.BytesIO()
    sf.write(buf,audio,SAMPLE_RATE,format="WAV")
    buf.seek(0)
    return buf

def execute_command(text):
    for k,action in COMMANDS.items():
        if k in text:
            print(f"[명령 실행] {k}")
            action()
            return
    print(f"[인식] {text} (매핑 없음)")

def main():
    print("STT Voice Click Control")
    print("명령어: 클릭 / 우클릭 / 더블클릭")
    while True:
        try:
            wav=record_audio()
            with sr.AudioFile(wav) as source:
                audio=recognizer.record(source)
            text=recognizer.recognize_google(audio,language=LANGUAGE)
            print("[인식 결과]",text)
            threading.Thread(target=execute_command,args=(text,),daemon=True).start()
            time.sleep(0.2)
        except sr.UnknownValueError:
            print("[인식 실패]")
        except sr.RequestError as e:
            print("[Google STT 오류]",e)
        except KeyboardInterrupt:
            print("종료")
            break

if __name__=="__main__":
    main()
