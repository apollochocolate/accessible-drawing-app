# main.py

import cv2
import numpy as np
import asyncio
import websockets
import threading
import webbrowser
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler

from mode_manager import (
    process_mode_key,
    is_laser_only_mode
)

from keyboard_layout import KEY_MAP
from laser_detect import detect_red_laser
from renderer import draw_keyboard_overlay

from shortcut_manager import (
    process_key,
    reset_key_state,
    get_active_modifier,
    get_allowed_keys
)


# =========================
# 기본 화면 설정
# =========================
WIN_W = 640
WIN_H = 480

# 키보드/레이저를 비추는 카메라 번호
# 내장캠이 얼굴용이면, 보통 외장 웹캠은 1 또는 2
CAMERA_INDEX = 2

# Windows VS Code 기준
CAMERA_BACKEND = cv2.CAP_DSHOW

# Mac에서 실행하면 위 줄 대신 아래 줄 사용
# CAMERA_BACKEND = cv2.CAP_AVFOUNDATION


# =========================
# 레이저 인식 고정값
# =========================
# 예전에 트랙바에서 조절하던 값들을 고정값으로 넣은 것
H_LOW1 = 0
H_HIGH1 = 10

H_LOW2 = 160
H_HIGH2 = 180

S_MIN = 80
V_MIN = 100

BLUR_K = 5
AREA_MIN = 5


# =========================
# HTML / WebSocket 서버 설정
# =========================
HTTP_PORT = 5500
WS_PORT = 8765

# True = 레이저 인식 중, False = 레이저 없음
laser_state = False
clients = set()


async def ws_handler(websocket):
    clients.add(websocket)

    try:
        while True:
            await asyncio.sleep(1)

    finally:
        clients.discard(websocket)


async def broadcast_laser_state():
    while True:
        if clients:
            msg = "LASER_ON" if laser_state else "LASER_OFF"

            await asyncio.gather(
                *[client.send(msg) for client in clients],
                return_exceptions=True
            )

        await asyncio.sleep(0.05)


async def main_ws():
    async with websockets.serve(ws_handler, "127.0.0.1", WS_PORT):
        await broadcast_laser_state()


def start_ws():
    asyncio.run(main_ws())


def start_http():
    # main.py와 index_keyboard.html이 같은 keyboard 폴더 안에 있어야 함
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    server = HTTPServer(
        ("127.0.0.1", HTTP_PORT),
        SimpleHTTPRequestHandler
    )

    print(f"[HTTP] http://127.0.0.1:{HTTP_PORT}/index_keyboard.html")
    server.serve_forever()


threading.Thread(target=start_ws, daemon=True).start()
threading.Thread(target=start_http, daemon=True).start()

webbrowser.open(f"http://127.0.0.1:{HTTP_PORT}/index_keyboard.html")


# =========================
# 키 위치 찾기
# =========================
def get_key_at(x, y):
    for name, (x1, y1, x2, y2) in KEY_MAP.items():
        if x1 <= x <= x2 and y1 <= y <= y2:
            return name

    return None


# =========================
# 카메라 열기
# =========================
cap = cv2.VideoCapture(CAMERA_INDEX, CAMERA_BACKEND)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIN_W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WIN_H)

for _ in range(10):
    cap.read()


print("실행 중...")
print("q : 종료")
print(f"WebSocket : ws://127.0.0.1:{WS_PORT}")
print(f"HTML      : http://127.0.0.1:{HTTP_PORT}/index_keyboard.html")


# =========================
# 메인 루프
# =========================
while True:
    ret, frame = cap.read()

    if not ret or frame is None or frame.size == 0:
        frame = np.zeros((WIN_H, WIN_W, 3), dtype=np.uint8)

    frame = cv2.resize(frame, (WIN_W, WIN_H))

    # =========================
    # 레이저 검출
    # =========================
    cx, cy, mask = detect_red_laser(
        frame,
        H_LOW1,
        H_HIGH1,
        H_LOW2,
        H_HIGH2,
        S_MIN,
        V_MIN,
        BLUR_K,
        AREA_MIN
    )

    detected_key = None
    laser_detected = cx is not None and cy is not None

    # HTML 얼굴 제스처 화면으로 보내는 상태
    # 레이저가 잡히면 얼굴 인식 OFF
    # 레이저가 없으면 얼굴 인식 ON
    laser_state = laser_detected

    current_mode = is_laser_only_mode()

    # =========================
    # 레이저가 잡힌 경우
    # =========================
    if laser_detected:
        detected_key = get_key_at(cx, cy)

        active_modifier = get_active_modifier()

        if active_modifier is not None:
            allowed_keys = get_allowed_keys(active_modifier)

            modifier_keys = {
                "Ctrl": ["Ctrl"],
                "Shift": ["LShift", "RShift"],
                "Alt": ["Alt"],
                "Win": ["Win"]
            }

            allowed_all = (
                allowed_keys |
                set(modifier_keys.get(active_modifier, []))
            )

            if detected_key not in allowed_all:
                detected_key = None

        # Mode 키 처리
        process_mode_key(detected_key)

        current_mode = is_laser_only_mode()

        # 레이저 위치 표시
        cv2.circle(frame, (cx, cy), 8, (0, 0, 255), -1)
        cv2.circle(frame, (cx, cy), 12, (255, 255, 255), 2)

    else:
        # 레이저가 없으면 키 반복 상태 초기화
        reset_key_state()

    # =========================
    # 레이저 전용 모드
    # =========================
    if current_mode and laser_detected:
        text = f"({cx},{cy})"

        cv2.putText(
            frame,
            text,
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2
        )

    # =========================
    # 키보드 모드
    # =========================
    if not current_mode:
        if detected_key is not None:
            process_key(detected_key)
        else:
            reset_key_state()

    # =========================
    # 키보드 렌더링
    # =========================
    draw_keyboard_overlay(
        frame,
        KEY_MAP,
        detected_key,
        current_mode
    )

    # 얼굴 제스처 상태 표시
    if laser_detected:
        cv2.putText(
            frame,
            "FACE OFF",
            (500, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 255),
            2
        )
    else:
        cv2.putText(
            frame,
            "FACE ON",
            (500, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2
        )

    cv2.imshow("Laser Keyboard / Mouse Mode", frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break


cap.release()
cv2.destroyAllWindows()