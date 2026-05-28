import tkinter as tk
from tkinter import font
import json
import os
import threading

from openai import OpenAI


MODEL = "gpt-5"

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

def on_text_modified(event=None):
    if input_box.edit_modified():
        input_box.edit_modified(False)
        schedule_ai_update()

def get_basic_suggestions():
    return ["안녕하세요", "도와주세요", "화장실"]


def get_ai_suggestions(text):
    """
    실제 OpenAI API를 사용해서 추천 단어/문장을 받아오는 함수.
    """

    text = text.strip()

    if text == "":
        return get_basic_suggestions()

    if client is None:
        return ["API 키 없음", "환경변수 확인", "OPENAI_API_KEY"]

    try:
        response = client.responses.create(
            model=MODEL,
            reasoning={"effort": "low"},
            instructions="""
너는 장애인 의사소통 보조 입력기의 AI 단어 추천 엔진이다.

사용자가 입력 중인 문장 또는 단어 일부를 보고,
다음에 올 가능성이 높은 한국어 또는 영어 표현 3개를 추천해라.

규칙:
- 추천은 반드시 3개만 한다.
- 너무 긴 문장은 피한다.
- 일상 의사소통에 필요한 표현을 우선한다.
- 사용자가 한글로 입력하면 한글 추천을 우선한다.
- 사용자가 영어로 입력하면 영어 추천을 우선한다.
- 장애인 사용자가 빠르게 선택할 수 있도록 짧고 명확하게 만든다.
- 설명은 하지 않는다.
""",
            input=f"""
현재 사용자가 입력 중인 내용:
{text}

이 입력 뒤에 이어질 수 있는 추천 단어 또는 짧은 문장 3개를 만들어줘.
""",
            text={
                "format": {
                    "type": "json_schema",
                    "name": "word_suggestions",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "suggestions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 3,
                                "maxItems": 3
                            }
                        },
                        "required": ["suggestions"],
                        "additionalProperties": False
                    },
                    "strict": True
                }
            },
            max_output_tokens=120
        )

        result = json.loads(response.output_text)
        suggestions = result.get("suggestions", [])

        clean_suggestions = []

        for item in suggestions:
            item = str(item).strip()
            if item and item not in clean_suggestions:
                clean_suggestions.append(item)

        while len(clean_suggestions) < 3:
            clean_suggestions.append("도와주세요")

        return clean_suggestions[:3]

    except Exception as e:
        print("AI 추천 오류:", e)
        return ["다시 시도", "도와주세요", "천천히 말할게요"]


def schedule_ai_update(event=None):
    """
    글자를 칠 때마다 바로 API를 부르면 너무 많이 호출됨.
    그래서 0.8초 동안 입력이 멈췄을 때만 AI를 호출하게 함.
    """

    global after_id

    if after_id is not None:
        root.after_cancel(after_id)

    after_id = root.after(800, start_ai_thread)


def start_ai_thread():
    text = input_box.get("1.0", tk.END).strip()

    status_label.config(text="AI 추천 생성 중...")

    thread = threading.Thread(
        target=update_suggestions_from_ai,
        args=(text,),
        daemon=True
    )
    thread.start()


def update_suggestions_from_ai(text):
    suggestions = get_ai_suggestions(text)

    root.after(0, lambda: apply_suggestions_to_buttons(suggestions))


def apply_suggestions_to_buttons(suggestions):
    for i, suggestion in enumerate(suggestions):
        suggestion_buttons[i].config(text=suggestion)

    status_label.config(text="추천 단어를 선택하면 자동 입력됩니다.")


def apply_suggestion(index):
    suggestion = suggestion_buttons[index].cget("text")

    if suggestion in ["API 키 없음", "환경변수 확인", "OPENAI_API_KEY"]:
        return

    current_text = input_box.get("1.0", tk.END).strip()

    if current_text:
        new_text = current_text + " " + suggestion + " "
    else:
        new_text = suggestion + " "

    input_box.delete("1.0", tk.END)
    input_box.insert(tk.END, new_text)

    schedule_ai_update()


def clear_text():
    input_box.delete("1.0", tk.END)
    apply_suggestions_to_buttons(get_basic_suggestions())


def read_text():
    text = input_box.get("1.0", tk.END).strip()
    print("읽어주기:", text)


root = tk.Tk()
root.title("AI 단어 추천 입력기")
root.geometry("750x620")
root.configure(bg="#f4f6f8")

after_id = None

title_font = font.Font(size=22, weight="bold")
text_font = font.Font(size=24)
button_font = font.Font(size=17, weight="bold")
small_font = font.Font(size=12)

title_label = tk.Label(
    root,
    text="AI 기반 단어 추천 입력기",
    font=title_font,
    bg="#f4f6f8"
)
title_label.pack(pady=18)

status_label = tk.Label(
    root,
    text="입력하면 AI가 추천 단어를 생성합니다.",
    font=small_font,
    bg="#f4f6f8",
    fg="#555555"
)
status_label.pack(pady=3)

input_box = tk.Text(
    root,
    height=8,
    font=text_font,
    wrap="word",
    padx=20,
    pady=20
)
input_box.pack(fill="both", expand=True, padx=30, pady=10)
input_box.bind("<<Modified>>", on_text_modified)

control_frame = tk.Frame(root, bg="#f4f6f8")
control_frame.pack(pady=10)

clear_button = tk.Button(
    control_frame,
    text="지우기",
    font=button_font,
    command=clear_text,
    width=10,
    height=2
)
clear_button.grid(row=0, column=0, padx=10)

read_button = tk.Button(
    control_frame,
    text="읽어주기",
    font=button_font,
    command=read_text,
    width=10,
    height=2
)
read_button.grid(row=0, column=1, padx=10)

suggestion_frame = tk.Frame(root, bg="#ffffff", height=140)
suggestion_frame.pack(side="bottom", fill="x")

suggestion_label = tk.Label(
    suggestion_frame,
    text="AI 추천 단어",
    font=font.Font(size=16, weight="bold"),
    bg="#ffffff"
)
suggestion_label.pack(pady=8)

button_frame = tk.Frame(suggestion_frame, bg="#ffffff")
button_frame.pack(pady=5)

suggestion_buttons = []

for i in range(3):
    btn = tk.Button(
        button_frame,
        text="",
        font=button_font,
        width=17,
        height=2,
        bg="#222222",
        fg="white",
        activebackground="#444444",
        activeforeground="white",
        command=lambda idx=i: apply_suggestion(idx)
    )
    btn.grid(row=0, column=i, padx=8)
    suggestion_buttons.append(btn)

apply_suggestions_to_buttons(get_basic_suggestions())

root.mainloop()