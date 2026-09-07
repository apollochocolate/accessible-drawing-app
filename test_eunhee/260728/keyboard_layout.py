WIN_W, WIN_H = 640, 480

U = 28
H = 42
GAP = 2
KB_X = 80
KB_Y = 20

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

RY = [KB_Y + i * (H + GAP) for i in range(6)]

x = KB_X
x = add_key("Esc", x, RY[0], int(U * 1.0))
x += 4
for f in ["F1", "F2", "F3", "F4"]:
    x = add_key(f, x, RY[0], int(U * 0.88))
x += 4
for f in ["F5", "F6", "F7", "F8"]:
    x = add_key(f, x, RY[0], int(U * 0.88))
x += 4
for f in ["F9", "F10", "F11", "F12"]:
    x = add_key(f, x, RY[0], int(U * 0.88))
x += 6
for f in ["PrtScr", "Ins", "Del"]:
    x = add_key(f, x, RY[0], int(U * 0.95))

make_row([
    ("`", 1), ("1", 1), ("2", 1), ("3", 1), ("4", 1), ("5", 1), ("6", 1),
    ("7", 1), ("8", 1), ("9", 1), ("0", 1), ("-", 1), ("=", 1), ("BkSp", 1.9)
], KB_X, RY[1])

make_row([
    ("Tab", 1.4), ("Q", 1), ("W", 1), ("E", 1), ("R", 1), ("T", 1),
    ("Y", 1), ("U", 1), ("I", 1), ("O", 1), ("P", 1), ("[", 1), ("]", 1), ("\\", 1.4)
], KB_X, RY[2])

make_row([
    ("Caps", 1.65), ("A", 1), ("S", 1), ("D", 1), ("F", 1), ("G", 1),
    ("H", 1), ("J", 1), ("K", 1), ("L", 1), (";", 1), ("'", 1), ("Enter", 2.05)
], KB_X, RY[3])

make_row([
    ("LShift", 2.1), ("Z", 1), ("X", 1), ("C", 1), ("V", 1), ("B", 1),
    ("N", 1), ("M", 1), (",", 1), (".", 1), ("/", 1), ("RShift", 1.9)
], KB_X, RY[4])

rs = KEY_MAP["RShift"]
add_key("Up", rs[2] + GAP, RY[4], int(U * 1.05))

make_row([
    ("LCtrl", 1.3), ("Fn", 1.0), ("Win", 1.1), ("LAlt", 1.1), ("Space", 4.1),
    ("Voice", 1.1), ("한자", 1.2), ("한/영", 1.3), ("Left", 1.05), ("Down", 1.05), ("Right", 1.05)
], KB_X, RY[5])
