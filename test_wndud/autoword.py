import tkinter as tk

# =========================
# 단어 사전
# =========================
WORDS = [
    "안녕하세요",
    "안녕",
    "안전",
    "안내",
    "안경",
    "가방",
    "가게",
    "가족",
    "가수",
    "가위",
    "학교",
    "학생",
    "학습",
    "한국",
    "한글",
    "사랑",
    "사람",
    "사진",
    "사용",
    "시간"
]

# =========================
# 추천 검색
# =========================
def get_suggestions(text):

    if not text:
        return []

    result = []

    for word in WORDS:
        if word.startswith(text):
            result.append(word)

    return result[:8]


# =========================
# 팝업 표시
# =========================
def show_popup(suggestions):

    if not suggestions:
        popup.withdraw()
        return

    listbox.delete(0, tk.END)

    for word in suggestions:
        listbox.insert(tk.END, word)

    root.update_idletasks()

    x = root.winfo_rootx() + entry.winfo_x()
    y = (
        root.winfo_rooty()
        + entry.winfo_y()
        + entry.winfo_height()
    )

    popup.geometry(f"300x220+{x}+{y}")
    popup.deiconify()
    popup.lift()


# =========================
# 입력 이벤트
# =========================
def on_key_release(event):

    text = entry.get().strip()

    suggestions = get_suggestions(text)

    show_popup(suggestions)


# =========================
# 단어 선택
# =========================
def select_word(event=None):

    selected = listbox.curselection()

    if not selected:
        return

    word = listbox.get(selected[0])

    entry.delete(0, tk.END)
    entry.insert(0, word)

    popup.withdraw()


# =========================
# 엔터 선택
# =========================
def on_listbox_enter(event):

    select_word()


# =========================
# GUI
# =========================
root = tk.Tk()

root.title("자동완성 팝업 테스트")
root.geometry("700x400")


title = tk.Label(
    root,
    text="단어 입력",
    font=("맑은 고딕", 16)
)

title.pack(pady=20)


entry = tk.Entry(
    root,
    font=("맑은 고딕", 24),
    width=25
)

entry.pack()

entry.bind(
    "<KeyRelease>",
    on_key_release
)


# =========================
# 팝업창
# =========================
popup = tk.Toplevel(root)

popup.withdraw()

popup.overrideredirect(True)

popup.attributes("-topmost", True)


listbox = tk.Listbox(
    popup,
    font=("맑은 고딕", 20),
    height=8,
    width=20
)

listbox.pack(
    fill="both",
    expand=True
)

listbox.bind(
    "<<ListboxSelect>>",
    select_word
)

listbox.bind(
    "<Return>",
    on_listbox_enter
)


# 시작 시 숨김
popup.withdraw()

root.mainloop()