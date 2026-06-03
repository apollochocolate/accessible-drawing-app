import tkinter as tk

# =====================================
# 단어 사전
# =====================================

WORDS = {
    "안녕하세요": 100,
    "안녕": 90,
    "안전": 80,
    "안내": 70,
    "안경": 60,

    "가방": 100,
    "가게": 90,
    "가족": 95,
    "가수": 70,
    "가위": 60,

    "학교": 100,
    "학생": 95,
    "학습": 80,
    "한국": 90,
    "한글": 85
}

current_suggestions = []
selected_index = 0
ghost_word = ""

# =====================================
# 추천 검색
# =====================================

def get_suggestions(text):

    if not text:
        return []

    result = []

    for word, score in WORDS.items():

        if word.startswith(text):
            result.append((word, score))

    result.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return [word for word, _ in result]


# =====================================
# Ghost Text
# =====================================

def update_ghost():

    global ghost_word

    text = entry_var.get()

    if not text:

        ghost_label.config(text="")
        ghost_word = ""

        return

    suggestions = get_suggestions(text)

    if not suggestions:

        ghost_label.config(text="")
        ghost_word = ""

        return

    best = suggestions[0]

    if best == text:

        ghost_label.config(text="")
        ghost_word = ""

        return

    remain = best[len(text):]

    ghost_word = best

    ghost_label.config(text=remain)


# =====================================
# 팝업 위치
# =====================================

def show_popup():

    root.update_idletasks()

    x = entry.winfo_rootx()

    y = (
        entry.winfo_rooty()
        + entry.winfo_height()
        + 2
    )

    popup.geometry(
        f"400x220+{x}+{y}"
    )

    popup.deiconify()
    popup.lift()


def hide_popup():

    popup.withdraw()


# =====================================
# 목록 갱신
# =====================================

def update_suggestions():

    global current_suggestions
    global selected_index

    text = entry_var.get().strip()

    current_suggestions = get_suggestions(text)

    listbox.delete(0, tk.END)

    if not current_suggestions:

        hide_popup()
        update_ghost()

        return

    for word in current_suggestions:

        listbox.insert(
            tk.END,
            word
        )

    selected_index = 0

    refresh_selection()

    show_popup()

    update_ghost()


# =====================================
# 선택 강조
# =====================================

def refresh_selection():

    if not current_suggestions:
        return

    listbox.selection_clear(
        0,
        tk.END
    )

    listbox.selection_set(
        selected_index
    )

    listbox.activate(
        selected_index
    )

    listbox.see(
        selected_index
    )


# =====================================
# 적용
# =====================================

def apply_selected():

    if not current_suggestions:
        return

    word = current_suggestions[
        selected_index
    ]

    entry_var.set(word)

    hide_popup()

    update_ghost()


# =====================================
# 방향키
# =====================================

def down_key(event):

    global selected_index

    if not current_suggestions:
        return "break"

    selected_index += 1

    if selected_index >= len(
        current_suggestions
    ):
        selected_index = 0

    refresh_selection()

    return "break"


def up_key(event):

    global selected_index

    if not current_suggestions:
        return "break"

    selected_index -= 1

    if selected_index < 0:
        selected_index = (
            len(current_suggestions)-1
        )

    refresh_selection()

    return "break"


# =====================================
# Enter
# =====================================

def enter_key(event):

    apply_selected()

    return "break"


# =====================================
# Tab
# =====================================

def tab_key(event):

    global ghost_word

    if ghost_word:

        entry_var.set(
            ghost_word
        )

        update_suggestions()

        hide_popup()

    return "break"


# =====================================
# 마우스
# =====================================

def mouse_select(event):

    global selected_index

    sel = listbox.curselection()

    if not sel:
        return

    selected_index = sel[0]

    apply_selected()


# =====================================
# 한글 입력 감시
# =====================================

def monitor():

    current = entry_var.get()

    if current != monitor.last:

        monitor.last = current

        update_suggestions()

    root.after(
        80,
        monitor
    )

monitor.last = ""


# =====================================
# GUI
# =====================================

root = tk.Tk()

root.title(
    "VSCode 스타일 자동완성"
)

root.geometry(
    "800x500"
)

title = tk.Label(
    root,
    text="단어 입력",
    font=("맑은 고딕",18)
)

title.pack(
    pady=20
)

# =========================
# Entry 영역
# =========================

entry_frame = tk.Frame(
    root
)

entry_frame.pack()

entry_var = tk.StringVar()

entry = tk.Entry(
    entry_frame,
    textvariable=entry_var,
    font=("맑은 고딕",26),
    width=20
)

entry.grid(
    row=0,
    column=0,
    sticky="w"
)

# Ghost Text

ghost_label = tk.Label(
    entry_frame,
    text="",
    fg="gray",
    font=("맑은 고딕",26)
)

ghost_label.grid(
    row=0,
    column=1,
    sticky="w"
)

entry.bind(
    "<Down>",
    down_key
)

entry.bind(
    "<Up>",
    up_key
)

entry.bind(
    "<Return>",
    enter_key
)

entry.bind(
    "<Tab>",
    tab_key
)

# =========================
# Popup
# =========================

popup = tk.Toplevel(
    root
)

popup.withdraw()

popup.overrideredirect(
    True
)

popup.attributes(
    "-topmost",
    True
)

listbox = tk.Listbox(
    popup,
    font=("맑은 고딕",18),
    height=8,
    activestyle="none",
    selectmode=tk.SINGLE
)

listbox.pack(
    fill="both",
    expand=True
)

listbox.bind(
    "<ButtonRelease-1>",
    mouse_select
)

monitor()

root.mainloop()