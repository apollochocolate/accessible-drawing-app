# keyboard_layout.py

U   = 36
H   = 60
GAP = 2

WIN_W, WIN_H = 640, 480

KB_ROWS    = 7
KB_TOTAL_H = KB_ROWS * (H + GAP)
KB_Y       = (WIN_H - KB_TOTAL_H) // 2
KB_X       = 40

KEY_MAP = {}

def add_key(name, x, y, w, h=H):
    KEY_MAP[name] = (x, y, x + w, y + h)
    return x + w + GAP

def make_row(keys_widths, start_x, row_y):
    x = start_x
    for name, ratio in keys_widths:
        w = max(int(U * ratio), 1)
        add_key(name, x, row_y, w)
        x += w + GAP

y0 = KB_Y
y1 = KB_Y + (H + GAP) * 1
y2 = KB_Y + (H + GAP) * 2
y3 = KB_Y + (H + GAP) * 3
y4 = KB_Y + (H + GAP) * 4
y5 = KB_Y + (H + GAP) * 5
y6 = KB_Y + (H + GAP) * 6

x = KB_X
x = add_key("Esc", x+2, y0, int(U*0.9))

for fname in ["F1","F2","F3","F4"]:
    x = add_key(fname, x+1, y0, int(U*0.88))

for fname in ["F5","F6","F7","F8"]:
    x = add_key(fname, x+1, y0, int(U*0.88))

for fname in ["F9","F10","F11","F12"]:
    x = add_key(fname, x+1, y0, int(U*0.88))

for fname in ["PrtScr","Ins","Del"]:
    x = add_key(fname, x+1, y0, int(U*0.95))

make_row([("`",1),("1",1),("2",1),("3",1),("4",1),("5",1),
          ("6",1),("7",1),("8",1),("9",1),("0",1),
          ("-",1),("=",1),("BkSp",1.9)], KB_X, y1)

make_row([("Tab",1.4),("Q",1),("W",1),("E",1),("R",1),
          ("T",1),("Y",1),("U",1),("I",1),("O",1),
          ("P",1),("[",1),("]",1),("\\",1.4)], KB_X, y2)

make_row([("Caps",1.65),("A",1),("S",1),("D",1),("F",1),
          ("G",1),("H",1),("J",1),("K",1),("L",1),
          (";",1),("'",1),("Enter",2.05)], KB_X, y3)

make_row([("LShift",2.1),("Z",1),("X",1),("C",1),("V",1),
          ("B",1),("N",1),("M",1),(",",1),(".",1),
          ("/",1),("RShift",2.6)], KB_X, y4)

make_row([("LCtrl",1.3),("LAlt",1.1),("Space",5.9),
          ("RAlt",1.1),("RCtrl",1.3)], KB_X, y5)


bottom_keys = [
    ("Mode", 1.6),
    ("Fn",   1.3),
    ("�쒖옄", 1.4),
    ("Win",  1.4),
    ("��/��",1.4),
]

x = KB_X

for name, ratio in bottom_keys:
    w = int(U * ratio)
    add_key(name, x, y6, w)
    x += w + GAP


ARR_UNIT = int(U * 1.05)

rc_x1, rc_y1, rc_x2, rc_y2 = KEY_MAP["RCtrl"]

ARR_X = rc_x2 + 2

up_x = ARR_X + ARR_UNIT + GAP

add_key("Up",    up_x,                     y5, ARR_UNIT, H)
add_key("Left",  ARR_X,                    y6, ARR_UNIT, H)
add_key("Down",  ARR_X + ARR_UNIT + GAP,   y6, ARR_UNIT, H)
add_key("Right", ARR_X + (ARR_UNIT+GAP)*2, y6, ARR_UNIT, H)

def get_key_at(x, y):
    for name, (x1,y1,x2,y2) in KEY_MAP.items():
        if x1 <= x <= x2 and y1 <= y <= y2:
            return name
    return None