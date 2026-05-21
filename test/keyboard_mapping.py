import cv2
import numpy as np
from PIL import ImageFont, ImageDraw, Image

WIN_W, WIN_H = 640, 480

U   = 36
H   = 60
GAP = 2

KB_ROWS    = 7
KB_TOTAL_H = KB_ROWS * (H + GAP)
KB_Y       = (WIN_H - KB_TOTAL_H) // 2
KB_X       = 8

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

# Row 0: Esc + F1~F12 + PrtScr + Ins + Del
x = KB_X
x = add_key("Esc", x, y0, int(U*1.0))
x += 4
for fname in ["F1","F2","F3","F4"]:
    x = add_key(fname, x, y0, int(U*0.88))
x += 4
for fname in ["F5","F6","F7","F8"]:
    x = add_key(fname, x, y0, int(U*0.88))
x += 4
for fname in ["F9","F10","F11","F12"]:
    x = add_key(fname, x, y0, int(U*0.88))
x += 6
for fname in ["PrtScr","Ins","Del"]:
    x = add_key(fname, x, y0, int(U*0.95))

make_row([("`",1),("1",1),("2",1),("3",1),("4",1),("5",1),
          ("6",1),("7",1),("8",1),("9",1),("0",1),("-",1),("=",1),("BkSp",1.9)], KB_X, y1)
make_row([("Tab",1.4),("Q",1),("W",1),("E",1),("R",1),("T",1),
          ("Y",1),("U",1),("I",1),("O",1),("P",1),("[",1),("]",1),("\\",1.4)], KB_X, y2)
make_row([("Caps",1.65),("A",1),("S",1),("D",1),("F",1),("G",1),
          ("H",1),("J",1),("K",1),("L",1),(";",1),("'",1),("Enter",2.05)], KB_X, y3)
make_row([("LShift",2.1),("Z",1),("X",1),("C",1),("V",1),("B",1),
          ("N",1),("M",1),(",",1),(".",1),("/",1),("RShift",2.6)], KB_X, y4)
make_row([("LCtrl",1.3),("LAlt",1.1),("Space",5.9),("RAlt",1.1),("RCtrl",1.3)], KB_X, y5)

ARR_UNIT = int(U * 1.05)

# RCtrl 위치 가져오기
rc_x1, rc_y1, rc_x2, rc_y2 = KEY_MAP["RCtrl"]

# RCtrl 바로 오른쪽부터 방향키 시작
ARR_X = rc_x2 + 10
fn_keys  = [("Mode",1.3),("Fn",1.3),("한자",1.4),("Win",1.4),("한/영",1.4)]
x = KB_X
for name, ratio in fn_keys:
    w = int(U * ratio)
    add_key(name, x, y6, w)
    x += w + GAP

up_x = ARR_X + ARR_UNIT + GAP
add_key("Up",    up_x,                     y5, ARR_UNIT, H)
add_key("Left",  ARR_X,                    y6, ARR_UNIT, H)
add_key("Down",  ARR_X + ARR_UNIT + GAP,   y6, ARR_UNIT, H)
add_key("Right", ARR_X + (ARR_UNIT+GAP)*2, y6, ARR_UNIT, H)

# ═══════════════════════════════════════════════
# PIL 폰트 로드 (한국어 + 유니코드 지원)
# ═══════════════════════════════════════════════
def load_font(size):
    candidates = [

        # Windows
        "C:/Windows/Fonts/malgun.ttf",     # 맑은 고딕
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

FONT_SM = load_font(11)
FONT_MD = load_font(13)
FONT_LG = load_font(15)

def put_text_pil(frame, text, cx, cy, font, color=(205,205,215)):
    """PIL로 텍스트를 그려서 OpenCV 프레임에 합성 (한국어/유니코드 지원)"""
    img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw    = ImageDraw.Draw(img_pil)
    bbox    = draw.textbbox((0,0), text, font=font)
    tw, th  = bbox[2]-bbox[0], bbox[3]-bbox[1]
    draw.text((cx - tw//2, cy - th//2), text, font=font, fill=(color[2],color[1],color[0]))
    frame[:] = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

# ═══════════════════════════════════════════════
# 레이저 검출
# ═══════════════════════════════════════════════
def detect_red_laser(frame, h_lo, h_hi, h_lo2, h_hi2, s_min, v_min, blur_k, area_min):
    k = blur_k if blur_k % 2 == 1 else blur_k + 1
    k = max(k, 1)
    blurred = cv2.GaussianBlur(frame, (k, k), 0)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
    m1 = cv2.inRange(hsv, np.array([h_lo,  s_min, v_min]), np.array([h_hi,  255, 255]))
    m2 = cv2.inRange(hsv, np.array([h_lo2, s_min, v_min]), np.array([h_hi2, 255, 255]))
    hsv_mask = cv2.bitwise_or(m1, m2)
    v_channel = hsv[:,:,2]
    _, bright_mask = cv2.threshold(v_channel, v_min, 255, cv2.THRESH_BINARY)
    combined = cv2.bitwise_and(hsv_mask, bright_mask)
    kernel = np.ones((3,3), np.uint8)
    combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN,   kernel)
    combined = cv2.morphologyEx(combined, cv2.MORPH_DILATE, kernel, iterations=2)
    contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        lc = max(contours, key=cv2.contourArea)
        if cv2.contourArea(lc) > area_min:
            M = cv2.moments(lc)
            if M["m00"] != 0:
                return int(M["m10"]/M["m00"]), int(M["m01"]/M["m00"]), combined
    return None, None, combined

def get_key_at(x, y):
    for name, (x1,y1,x2,y2) in KEY_MAP.items():
        if x1 <= x <= x2 and y1 <= y <= y2:
            return name
    return None

# ═══════════════════════════════════════════════
# 키 라벨 정의
# ═══════════════════════════════════════════════
LABEL_MAP = {
    "BkSp":"BkSp",   "LShift":"Shift",  "RShift":"Shift",
    "LCtrl":"Ctrl",  "RCtrl":"Ctrl",    "LAlt":"Alt",    "RAlt":"Alt",
    "\\":"\\",   "Space":"Space",
    "Up":"↑",        "Down":"↓",        "Left":"←",      "Right":"→",
    "PrtScr":"PrtScr","Ins":"Ins",      "Del":"Del",
    "Mode": "Mode", "한자":"한자",   "한/영":"한/영",   "Win":"Win",     "Fn":"Fn",
}

SPECIAL = {"Esc","BkSp","Tab","Caps","LShift","RShift","LCtrl","RCtrl",
           "LAlt","RAlt","Enter","Space","Fn","Mode","한자","Win","한/영",
           "PrtScr","Ins","Del"}
FKEYS   = {"F1","F2","F3","F4","F5","F6","F7","F8","F9","F10","F11","F12"}
ARROWS  = {"Up","Down","Left","Right"}

# 길이에 따라 폰트 크기 선택
def pick_font(label):
    if len(label) >= 5:  return FONT_SM
    if len(label) >= 3:  return FONT_MD
    return FONT_LG

def draw_keyboard_overlay(frame, hovered):
    overlay = frame.copy()
    for name, (x1,y1,x2,y2) in KEY_MAP.items():
        if name == hovered:       bg = (60, 210, 100)
        elif name in ARROWS:      bg = (70, 50, 90)
        elif name in SPECIAL:     bg = (55, 55, 85)
        elif name in FKEYS:       bg = (45, 45, 68)
        else:                     bg = (38, 38, 52)
        cv2.rectangle(overlay, (x1,y1), (x2,y2), bg, -1)
        cv2.rectangle(overlay, (x1,y1), (x2,y2), (120,120,150), 1)

    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    # 텍스트는 PIL로 별도 렌더링 (한국어/유니코드 지원)
    for name, (x1,y1,x2,y2) in KEY_MAP.items():
        label = LABEL_MAP.get(name, name)
        tc    = (255,255,255) if name == hovered else (205,205,215)
        font  = pick_font(label)
        cx    = (x1+x2)//2
        cy    = (y1+y2)//2
        put_text_pil(frame, label, cx, cy, font, tc)

# ═══════════════════════════════════════════════
# 트랙바 창
# ═══════════════════════════════════════════════
TUNE_WIN = "[ HSV Tuning ] - q:quit  m:mask on/off"
cv2.namedWindow(TUNE_WIN)
cv2.resizeWindow(TUNE_WIN, 600, 350)

cv2.createTrackbar("H_low1",  TUNE_WIN, 0,   10,  lambda x: None)
cv2.createTrackbar("H_high1", TUNE_WIN, 10,  30,  lambda x: None)
cv2.createTrackbar("H_low2",  TUNE_WIN, 160, 180, lambda x: None)
cv2.createTrackbar("H_high2", TUNE_WIN, 180, 180, lambda x: None)
cv2.createTrackbar("S_min",   TUNE_WIN, 80,  255, lambda x: None)
cv2.createTrackbar("V_min",   TUNE_WIN, 100, 255, lambda x: None)
cv2.createTrackbar("Blur",    TUNE_WIN, 5,   21,  lambda x: None)
cv2.createTrackbar("Area",    TUNE_WIN, 5,   200, lambda x: None)

cap = cv2.VideoCapture(1)

if not cap.isOpened():
    print("카메라를 열 수 없습니다.")
    exit()

cap.set(cv2.CAP_PROP_FRAME_WIDTH,  WIN_W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WIN_H)

show_mask = False
print("실행 중... q:종료 / m:마스크 창 on/off")
print("=== 트랙바 설명 ===")
print("H_low1  : 붉은색 범위1 하한  (기본  0)")
print("H_high1 : 붉은색 범위1 상한  (기본 10)")
print("H_low2  : 붉은색 범위2 하한  (기본 160)")
print("H_high2 : 붉은색 범위2 상한  (기본 180)")
print("S_min   : 채도 최솟값        (기본  80)")
print("V_min   : 밝기 최솟값        (기본 100)")
print("Blur    : 블러 강도          (기본   5)")
print("Area    : 최소 감지 면적     (기본   5)")

while True:
    ret, frame = cap.read()

    if not ret:
        frame = np.zeros((WIN_H, WIN_W, 3), dtype=np.uint8)

    # 먼저 크기 조정
    frame = cv2.resize(frame, (WIN_W, WIN_H))

    # 좌우 반전 (거울 모드)
    #frame = cv2.flip(frame, 1)

    h_lo   = cv2.getTrackbarPos("H_low1",  TUNE_WIN)
    h_hi   = cv2.getTrackbarPos("H_high1", TUNE_WIN)
    h_lo2  = cv2.getTrackbarPos("H_low2",  TUNE_WIN)
    h_hi2  = cv2.getTrackbarPos("H_high2", TUNE_WIN)
    s_min  = cv2.getTrackbarPos("S_min",   TUNE_WIN)
    v_min  = cv2.getTrackbarPos("V_min",   TUNE_WIN)
    blur_k = max(cv2.getTrackbarPos("Blur", TUNE_WIN), 1)
    area_m = cv2.getTrackbarPos("Area",    TUNE_WIN)

    cx, cy, mask = detect_red_laser(frame, h_lo, h_hi, h_lo2, h_hi2, s_min, v_min, blur_k, area_m)
    detected_key = None

    if cx is not None:
        detected_key = get_key_at(cx, cy)
        cv2.circle(frame, (cx,cy), 8,  (0,0,255), -1)
        cv2.circle(frame, (cx,cy), 12, (255,255,255), 2)

    draw_keyboard_overlay(frame, detected_key)

    # 인식 상태 (좌하단)
    status = f"Key: {detected_key}" if detected_key else "Key: ---"
    cv2.rectangle(frame, (0, WIN_H-32), (220, WIN_H), (0,0,0), -1)
    put_text_pil(frame, status, 110, WIN_H-16, FONT_MD, (0,255,180))

    # 레이저 감지 여부 (우상단)
    dot_color = (0,255,0) if cx is not None else (0,0,255)
    dot_label = "LASER ON" if cx is not None else "NO LASER"
    cv2.circle(frame, (WIN_W-90, 18), 8, dot_color, -1)
    cv2.putText(frame, dot_label, (WIN_W-78, 23),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, dot_color, 1, cv2.LINE_AA)

    if detected_key:
        print(f"인식된 키: {detected_key}")

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

cap.release()
cv2.destroyAllWindows()

