import cv2
import numpy as np
from PIL import ImageFont, ImageDraw, Image
import asyncio
import websockets
import threading
import webbrowser
import os
import time
import json
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler


# =========================
# WebSocket / HTTP 설정
# =========================
laser_state = False
current_key = None
clients = set()
state_lock = threading.Lock()

HTTP_PORT = 5500
WS_PORT = 8765


async def ws_handler(websocket):
    clients.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        clients.discard(websocket)


async def broadcast_state():
    last_msg = None
    while True:
        with state_lock:
            msg = "LASER_ON" if laser_state else "LASER_OFF"
        if clients and msg != last_msg:
            await asyncio.gather(
                *[c.send(msg) for c in clients],
                return_exceptions=True,
            )
            last_msg = msg
        await asyncio.sleep(0.05)


async def main_ws():
    async with websockets.serve(ws_handler, "127.0.0.1", WS_PORT):
        await broadcast_state()


def start_ws():
    asyncio.run(main_ws())


def start_http():
    base = os.path.dirname(os.path.abspath(__file__))
    handler = partial(SimpleHTTPRequestHandler, directory=base)
    server = HTTPServer(("127.0.0.1", HTTP_PORT), handler)
    print(f"HTTP server: http://127.0.0.1:{HTTP_PORT}/index_keyboard.html")
    server.serve_forever()


threading.Thread(target=start_ws, daemon=True).start()
threading.Thread(target=start_http, daemon=True).start()

time.sleep(0.4)
webbrowser.open(f"http://127.0.0.1:{HTTP_PORT}/index_keyboard.html")


# =========================
# 키보드 레이아웃
# =========================
WIN_W, WIN_H = 640, 480
U = 36
H = 60
GAP = 2

KB_ROWS = 7
KB_TOTAL_H = KB_ROWS * (H + GAP)
KB_Y = (WIN_H - KB_TOTAL_H) // 2
KB_X = 8

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


ys = [KB_Y + (H + GAP) * i for i in range(7)]
y0, y1, y2, y3, y4, y5, y6 = ys

# Row 0 (function row)
x = KB_X
x = add_key("Esc", x, y0, int(U * 1.0)) + 4
for fname in ["F1", "F2", "F3", "F4"]:
    x = add_key(fname, x, y0, int(U * 0.88))
x += 4
for fname in ["F5", "F6", "F7", "F8"]:
    x = add_key(fname, x, y0, int(U * 0.88))
x += 4
for fname in ["F9", "F10", "F11", "F12"]:
    x = add_key(fname, x, y0, int(U * 0.88))
x += 6
for fname in ["PrtScr", "Ins", "Del"]:
    x = add_key(fname, x, y0, int(U * 0.95))

make_row([("`",1),("1",1),("2",1),("3",1),("4",1),("5",1),("6",1),
          ("7",1),("8",1),("9",1),("0",1),("-",1),("=",1),("BkSp",1.9)], KB_X, y1)
make_row([("Tab",1.4),("Q",1),("W",1),("E",1),("R",1),("T",1),("Y",1),
          ("U",1),("I",1),("O",1),("P",1),("[",1),("]",1),("\\",1.4)], KB_X, y2)
make_row([("Caps",1.65),("A",1),("S",1),("D",1),("F",1),("G",1),("H",1),
          ("J",1),("K",1),("L",1),(";",1),("'",1),("Enter",2.05)], KB_X, y3)
make_row([("LShift",2.1),("Z",1),("X",1),("C",1),("V",1),("B",1),("N",1),
          ("M",1),(",",1),(".",1),("/",1),("RShift",2.6)], KB_X, y4)
make_row([("LCtrl",1.3),("LAlt",1.1),("Space",5.9),("RAlt",1.1),("RCtrl",1.3)], KB_X, y5)

ARR_UNIT = int(U * 1.05)
rc_x1, rc_y1, rc_x2, rc_y2 = KEY_MAP["RCtrl"]
ARR_X = rc_x2 + 10

x = KB_X
for name, ratio in [("Fn",1.3),("한자",1.4),("Win",1.4),("한/영",1.4)]:
    w = int(U * ratio)
    add_key(name, x, y6, w)
    x += w + GAP

add_key("Up",    ARR_X + ARR_UNIT + GAP, y5, ARR_UNIT, H)
add_key("Left",  ARR_X,                   y6, ARR_UNIT, H)
add_key("Down",  ARR_X + ARR_UNIT + GAP,  y6, ARR_UNIT, H)
add_key("Right", ARR_X + (ARR_UNIT+GAP)*2, y6, ARR_UNIT, H)


# =========================
# 폰트
# =========================
def load_font(size):
    for path in [
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/gulim.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except:
            pass
    return ImageFont.load_default()


FONT_SM = load_font(11)
FONT_MD = load_font(13)
FONT_LG = load_font(15)


# =========================
# 레이저 검출 (강화된 필터)
# =========================
def detect_red_laser(frame, h_lo, h_hi, h_lo2, h_hi2,
                     s_min, v_min, blur_k, area_min, area_max=2000):
    k = blur_k if blur_k % 2 == 1 else blur_k + 1
    k = max(k, 1)

    blurred = cv2.GaussianBlur(frame, (k, k), 0)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

    m1 = cv2.inRange(hsv, np.array([h_lo, s_min, v_min]),
                          np.array([h_hi, 255, 255]))
    m2 = cv2.inRange(hsv, np.array([h_lo2, s_min, v_min]),
                          np.array([h_hi2, 255, 255]))
    mask = cv2.bitwise_or(m1, m2)

    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best = None
    best_score = 0
    for c in contours:
        area = cv2.contourArea(c)
        if area < area_min or area > area_max:
            continue
        M = cv2.moments(c)
        if M["m00"] == 0:
            continue
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        # 레이저 특성: 중심부 V가 매우 밝아야 함
        v_center = int(hsv[cy, cx, 2])
        if v_center < 220:
            continue
        score = v_center + area * 0.5
        if score > best_score:
            best_score = score
            best = (cx, cy)

    if best:
        return best[0], best[1], mask
    return None, None, mask


def get_key_at(x, y):
    for name, (x1, y1, x2, y2) in KEY_MAP.items():
        if x1 <= x <= x2 and y1 <= y <= y2:
            return name
    return None


# =========================
# 키 라벨
# =========================
LABEL_MAP = {
    "BkSp":"BkSp","LShift":"Shift","RShift":"Shift",
    "LCtrl":"Ctrl","RCtrl":"Ctrl","LAlt":"Alt","RAlt":"Alt",
    "Up":"↑","Down":"↓","Left":"←","Right":"→",
}
SPECIAL = {"Esc","BkSp","Tab","Caps","LShift","RShift","LCtrl","RCtrl",
           "LAlt","RAlt","Enter","Space","Fn","한자","Win","한/영",
           "PrtScr","Ins","Del"}
FKEYS = {f"F{i}" for i in range(1,13)}
ARROWS = {"Up","Down","Left","Right"}


def pick_font(label):
    if len(label) >= 5: return FONT_SM
    if len(label) >= 3: return FONT_MD
    return FONT_LG


def draw_keyboard_overlay(frame, hovered, confirmed):
    overlay = frame.copy()
    for name, (x1, y1, x2, y2) in KEY_MAP.items():
        if name == confirmed:
            bg = (60, 210, 100)
        elif name == hovered:
            bg = (40, 140, 200)
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

    # PIL 변환을 한 번만 수행 (FPS 개선)
    img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    for name, (x1, y1, x2, y2) in KEY_MAP.items():
        label = LABEL_MAP.get(name, name)
        tc = (255, 255, 255) if name in (hovered, confirmed) else (215, 215, 225)
        font = pick_font(label)
        bbox = draw.textbbox((0, 0), label, font=font)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        cx = (x1+x2)//2 - tw//2
        cy = (y1+y2)//2 - th//2
        draw.text((cx, cy), label, font=font, fill=tc)
    frame[:] = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


# =========================
# 트랙바
# =========================
TUNE_WIN = "[ HSV Tuning ] - q:quit  m:mask on/off"
cv2.namedWindow(TUNE_WIN)
cv2.resizeWindow(TUNE_WIN, 600, 380)

cv2.createTrackbar("H_low1",  TUNE_WIN, 0,   30,  lambda x: None)
cv2.createTrackbar("H_high1", TUNE_WIN, 10,  30,  lambda x: None)
cv2.createTrackbar("H_low2",  TUNE_WIN, 160, 180, lambda x: None)
cv2.createTrackbar("H_high2", TUNE_WIN, 180, 180, lambda x: None)
cv2.createTrackbar("S_min",   TUNE_WIN, 80,  255, lambda x: None)
cv2.createTrackbar("V_min",   TUNE_WIN, 200, 255, lambda x: None)
cv2.createTrackbar("Blur",    TUNE_WIN, 5,   21,  lambda x: None)
cv2.createTrackbar("AreaMin", TUNE_WIN, 5,   200, lambda x: None)
cv2.createTrackbar("HoldN",   TUNE_WIN, 3,   15,  lambda x: None)


# =========================
# 카메라 (fallback)
# =========================
def open_camera():
    for idx in [2, 0, 1]:
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if cap.isOpened():
            ok, _ = cap.read()
            if ok:
                print(f"[camera] opened index {idx}")
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIN_W)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WIN_H)
                return cap
            cap.release()
    return None


cap = open_camera()
if cap is None:
    print("[camera] 열기 실패. 빈 프레임으로 진행합니다.")

show_mask = False
print("실행 중... q:종료 / m:마스크 창 on/off")
print(f"WebSocket: ws://127.0.0.1:{WS_PORT}")
print(f"HTML:      http://127.0.0.1:{HTTP_PORT}/index_keyboard.html")


# =========================
# 메인 루프 (디바운싱)
# =========================
hover_key = None
hover_count = 0
confirmed_key = None

while True:
    if cap is not None:
        ret, frame = cap.read()
        if not ret:
            frame = np.zeros((WIN_H, WIN_W, 3), dtype=np.uint8)
    else:
        frame = np.zeros((WIN_H, WIN_W, 3), dtype=np.uint8)

    frame = cv2.resize(frame, (WIN_W, WIN_H))

    h_lo  = cv2.getTrackbarPos("H_low1",  TUNE_WIN)
    h_hi  = cv2.getTrackbarPos("H_high1", TUNE_WIN)
    h_lo2 = cv2.getTrackbarPos("H_low2",  TUNE_WIN)
    h_hi2 = cv2.getTrackbarPos("H_high2", TUNE_WIN)
    s_min = cv2.getTrackbarPos("S_min",   TUNE_WIN)
    v_min = cv2.getTrackbarPos("V_min",   TUNE_WIN)
    blur_k = max(cv2.getTrackbarPos("Blur", TUNE_WIN), 1)
    area_m = max(cv2.getTrackbarPos("AreaMin", TUNE_WIN), 1)
    hold_n = max(cv2.getTrackbarPos("HoldN", TUNE_WIN), 1)

    cx, cy, mask = detect_red_laser(frame, h_lo, h_hi, h_lo2, h_hi2,
                                    s_min, v_min, blur_k, area_m)

    detected_now = cx is not None

    if detected_now:
        key_now = get_key_at(cx, cy)
        if key_now == hover_key and key_now is not None:
            hover_count += 1
        else:
            hover_key = key_now
            hover_count = 1
        confirmed_key = hover_key if hover_count >= hold_n else None
        cv2.circle(frame, (cx, cy), 8, (0, 0, 255), -1)
        cv2.circle(frame, (cx, cy), 12, (255, 255, 255), 2)
    else:
        hover_key = None
        hover_count = 0
        confirmed_key = None

    with state_lock:
        laser_state = detected_now
        current_key = confirmed_key

    draw_keyboard_overlay(frame, hover_key, confirmed_key)

    status = f"Key: {confirmed_key}" if confirmed_key else (
             f"Hover: {hover_key} ({hover_count}/{hold_n})" if hover_key else "Key: ---")
    cv2.rectangle(frame, (0, WIN_H-32), (260, WIN_H), (0, 0, 0), -1)

    img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    ImageDraw.Draw(img_pil).text((8, WIN_H-26), status, font=FONT_MD,
                                  fill=(180, 255, 0))
    frame[:] = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

    dot_color = (0, 255, 0) if detected_now else (0, 0, 255)
    dot_label = "LASER ON" if detected_now else "NO LASER"
    cv2.circle(frame, (WIN_W-105, 18), 8, dot_color, -1)
    cv2.putText(frame, dot_label, (WIN_W-92, 23),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, dot_color, 1, cv2.LINE_AA)

    if confirmed_key and hover_count == hold_n:
        print(f"[confirmed] {confirmed_key}")

    cv2.imshow("Laser Keyboard", frame)
    if show_mask:
        cv2.imshow("Mask Debug", mask)

    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break
    elif key == ord("m"):
        show_mask = not show_mask
        if not show_mask:
            cv2.destroyWindow("Mask Debug")
        print(f"마스크 창: {'ON' if show_mask else 'OFF'}")

if cap is not None:
    cap.release()
cv2.destroyAllWindows()
