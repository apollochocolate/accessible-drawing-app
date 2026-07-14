# renderer_updated.py
import cv2
import numpy as np
from PIL import ImageFont, ImageDraw, Image


def load_font(size):
    candidates = [
        # Windows
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/gulim.ttc",

        # Linux
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",

        # Mac
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/SFNS.ttf",
    ]

    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except:
            pass

    return ImageFont.load_default()


FONT_SM = load_font(9)
FONT_MD = load_font(10)
FONT_LG = load_font(12)
FONT_KO = load_font(8)
FONT_KO_SH = load_font(7)
FONT_SPEC = load_font(7)


def put_text_pil(frame, text, cx, cy, font, color=(205, 205, 215)):
    img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)

    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    draw.text(
        (cx - tw // 2, cy - th // 2),
        text,
        font=font,
        fill=(color[2], color[1], color[0])
    )

    frame[:] = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def put_text_xy(frame, text, x, y, font, color):
    img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    draw.text((x, y), text, font=font, fill=(color[2], color[1], color[0]))
    frame[:] = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def put_text_xyr(frame, text, x2, y, font, color):
    img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text((x2 - tw - 2, y), text, font=font, fill=(color[2], color[1], color[0]))
    frame[:] = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


KO_NORMAL = {
    "Q": "ㅂ", "W": "ㅈ", "E": "ㄷ", "R": "ㄱ", "T": "ㅅ",
    "Y": "ㅛ", "U": "ㅕ", "I": "ㅑ", "O": "ㅐ", "P": "ㅔ",
    "A": "ㅁ", "S": "ㄴ", "D": "ㅇ", "F": "ㄹ", "G": "ㅎ",
    "H": "ㅗ", "J": "ㅓ", "K": "ㅏ", "L": "ㅣ",
    "Z": "ㅋ", "X": "ㅌ", "C": "ㅊ", "V": "ㅍ", "B": "ㅠ", "N": "ㅜ", "M": "ㅡ",
}

KO_SHIFT = {
    "Q": "ㅃ", "W": "ㅉ", "E": "ㄸ", "R": "ㄲ", "T": "ㅆ", "O": "ㅒ", "P": "ㅖ"
}

SPEC_SHIFT = {
    "`": "~", "1": "!", "2": "@", "3": "#", "4": "$", "5": "%",
    "6": "^", "7": "&", "8": "*", "9": "(", "0": ")", "-": "_", "=": "+",
    "[": "{", "]": "}", "\\": "|", ";": ":", "'": '"', ",": "<", ".": ">", "/": "?"
}


LABEL_MAP = {
    "BkSp": "BkSp",
    "LShift": "Shift",
    "RShift": "Shift",
    "LCtrl": "Ctrl",
    "Ctrl": "Ctrl",
    "LAlt": "Alt",
    "Alt": "Alt",
    "\\": "\\",
    "Space": "Space",
    "Up": "↑",
    "Down": "↓",
    "Left": "←",
    "Right": "→",
    "PrtScr": "PrtSc",
    "Ins": "Ins",
    "Del": "Del",
    "Mode": "Mode",
    "한자": "한자",
    "한/영": "한/영",
    "Win": "Win",
    "Fn": "Fn",
    "Voice": "음성",
}


SPECIAL = {
    "Esc", "BkSp", "Tab", "Caps", "LShift", "RShift",
    "LCtrl", "Ctrl", "LAlt", "음성", "Alt",
    "Enter", "Space", "Fn", "Mode", "한자", "Win", "한/영",
    "PrtScr", "Ins", "Del"
}

FKEYS = {
    "F1", "F2", "F3", "F4", "F5", "F6",
    "F7", "F8", "F9", "F10", "F11", "F12"
}

ARROWS = {"Up", "Down", "Left", "Right"}


def pick_font(label):
    if len(label) >= 5:
        return FONT_SM
    if len(label) >= 3:
        return FONT_MD
    return FONT_LG


def draw_keyboard_overlay(frame, KEY_MAP, hovered=None):
    overlay = frame.copy()

    for name, (x1, y1, x2, y2) in KEY_MAP.items():
        if name == hovered:
            bg = (60, 210, 100)
        elif name in ARROWS:
            bg = (70, 50, 90)
        elif name in SPECIAL:
            bg = (55, 55, 85)
        elif name in FKEYS:
            bg = (45, 45, 68)
        else:
            bg = (38, 38, 52)

        cv2.rectangle(overlay, (x1, y1), (x2, y2), bg, -1)
        cv2.rectangle(overlay, (x1, y1), (x2, y2), (120, 120, 150), 1)

    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    for name, (x1, y1, x2, y2) in KEY_MAP.items():
        label = LABEL_MAP.get(name, name)
        tc = (255, 255, 255) if name == hovered else (205, 205, 215)
        font = pick_font(label)
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

        ko = KO_NORMAL.get(name)
        kosh = KO_SHIFT.get(name)
        sp = SPEC_SHIFT.get(name)

        if ko or kosh or sp:
            put_text_pil(frame, label, cx, cy + 5, font, tc)

            if sp:
                s_col = (100, 255, 255) if name == hovered else (80, 200, 255)
                put_text_xy(frame, sp, x1 + 3, y1 + 2, FONT_SPEC, s_col)

            if ko:
                k_col = (255, 220, 100) if name == hovered else (120, 200, 255)
                put_text_xyr(frame, ko, x2 - 2, y1 + 2, FONT_KO, k_col)

            if kosh:
                ks_col = (100, 255, 180) if name == hovered else (100, 160, 255)
                put_text_xy(frame, kosh, x1 + 3, y1 + 2, FONT_KO_SH, ks_col)
        else:
            put_text_pil(frame, label, cx, cy, font, tc)
