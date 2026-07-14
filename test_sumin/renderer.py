#renderer.py
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
        "/usr/share/fonts/truet 큮pe/nanum/NanumBarunGothic.ttf",

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


FONT_SM = load_font(11)
FONT_MD = load_font(13)
FONT_LG = load_font(15)


def put_text_pil(frame, text, cx, cy, font, color=(205,205,215)):

    img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)

    bbox = draw.textbbox((0,0), text, font=font)

    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    draw.text(
        (cx - tw//2, cy - th//2),
        text,
        font=font,
        fill=(color[2], color[1], color[0])
    )

    frame[:] = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)



LABEL_MAP = {

    "BkSp":"BkSp",

    "LShift":"Shift",
    "RShift":"Shift",

    "Ctrl":"Ctrl",

    "Alt":"Alt",

    "\\":"\\",

    "Space":"Space",

    "Up":"↑",
    "Down":"↓",
    "Left":"←",
    "Right":"→",

    "PrtScr":"PrtScr",
    "Ins":"Ins",
    "Del":"Del",

    "Mode":"Mode",
    "한자":"한자",
    "한/영":"한/영",
    "Win":"Win",
    "Fn":"Fn",
}


SPECIAL = {
    "Esc",
    "BkSp",
    "Tab",
    "Caps",

    "LShift",
    "RShift",

    "Ctrl",

    "Alt",


    "Enter",
    "Space",

    "Fn",
    "Mode",
    "한자",
    "Win",
    "한/영",

    "PrtScr",
    "Ins",
    "Del"
}

FKEYS = {
    "F1","F2","F3","F4",
    "F5","F6","F7","F8",
    "F9","F10","F11","F12"
}

ARROWS = {
    "Up",
    "Down",
    "Left",
    "Right"
}


def pick_font(label):

    if len(label) >= 5:
        return FONT_SM

    if len(label) >= 3:
        return FONT_MD

    return FONT_LG


def draw_keyboard_overlay(frame, KEY_MAP, hovered=None):

    # if laser_only:

    #     name = "Mode"

    #     x1, y1, x2, y2 = KEY_MAP[name]

       
    #     if hovered == "Mode":
    #         bg = (60, 210, 100)

    #     else:
    #         bg = (55, 55, 85)

 
    #     cv2.rectangle(
    #         frame,
    #         (x1, y1),
    #         (x2, y2),
    #         bg,
    #         -1
    #     )

    #     cv2.rectangle(
    #         frame,
    #         (x1, y1),
    #         (x2, y2),
    #         (180,180,220),
    #         2
    #     )

   
    #     label = LABEL_MAP.get(name, name)

    #     font = pick_font(label)

    #     cx = (x1 + x2) // 2
    #     cy = (y1 + y2) // 2

    #     put_text_pil(
    #         frame,
    #         label,
    #         cx,
    #         cy,
    #         font,
    #         (255,255,255)
    #     )

    #     return

    
    overlay = frame.copy()

    for name, (x1,y1,x2,y2) in KEY_MAP.items():
        cv2.line(
            frame,
            (35, 250),
            (605, 250),
            (120,120,140),
            2
        )

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

        cv2.rectangle(
            overlay,
            (x1,y1),
            (x2,y2),
            bg,
            -1
        )

        cv2.rectangle(
            overlay,
            (x1,y1),
            (x2,y2),
            (120,120,150),
            1
        )

    cv2.addWeighted(
        overlay,
        0.55,
        frame,
        0.45,
        0,
        frame
    )

    
    for name, (x1,y1,x2,y2) in KEY_MAP.items():

        label = LABEL_MAP.get(name, name)

        tc = (
            (255,255,255)
            if name == hovered
            else (205,205,215)
        )

        font = pick_font(label)

        cx = (x1+x2)//2
        cy = (y1+y2)//2

        put_text_pil(
            frame,
            label,
            cx,
            cy,
            font,
            tc
        )