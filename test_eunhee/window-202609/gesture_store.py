"""HTML에서 저장한 얼굴 제스처를 gestures.json으로 저장하고 기다리는 모듈."""

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from config_combined import (
    GESTURE_FILE,
    SETTINGS_SERVER_HOST,
    SETTINGS_SERVER_PORT,
    REQUIRED_GESTURE_IDS,
    REQUIRED_GESTURE_LABELS,
)


def load_gesture_settings():
    if not os.path.exists(GESTURE_FILE):
        raise FileNotFoundError(f"gestures.json 파일이 없습니다. 필요한 위치: {GESTURE_FILE}")

    with open(GESTURE_FILE, "r", encoding="utf-8") as f:
        settings = json.load(f)

    missing = []
    for gesture_id in REQUIRED_GESTURE_IDS:
        data = settings.get(gesture_id)
        if not isinstance(data, dict) or "vector" not in data:
            missing.append(REQUIRED_GESTURE_LABELS.get(gesture_id, gesture_id))

    if missing:
        raise ValueError("아직 저장되지 않은 제스처: " + ", ".join(missing))

    return settings


def save_gesture_settings(settings):
    with open(GESTURE_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


class GestureSaveHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "gesture_file": GESTURE_FILE})
            return

        if self.path != "/gestures":
            self._send_json(404, {"status": "not_found"})
            return

        if not os.path.exists(GESTURE_FILE):
            self._send_json(200, {"status": "empty", "settings": {}})
            return

        try:
            with open(GESTURE_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
            self._send_json(200, {"status": "ok", "settings": settings})
        except Exception as e:
            self._send_json(500, {"status": "error", "message": str(e)})

    def do_POST(self):
        if self.path != "/save_gestures":
            self._send_json(404, {"status": "not_found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            settings = json.loads(body or "{}")

            if not isinstance(settings, dict):
                self._send_json(400, {"status": "error", "message": "settings must be object"})
                return

            save_gesture_settings(settings)
            self._send_json(200, {"status": "ok", "saved_to": GESTURE_FILE})
            print(f"제스처 설정 자동 저장 완료: {GESTURE_FILE}")
        except Exception as e:
            self._send_json(500, {"status": "error", "message": str(e)})

    def log_message(self, format, *args):
        return


def start_gesture_save_server():
    server = ThreadingHTTPServer(
        (SETTINGS_SERVER_HOST, SETTINGS_SERVER_PORT),
        GestureSaveHandler,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print(
        f"제스처 자동 저장 서버 시작: "
        f"http://{SETTINGS_SERVER_HOST}:{SETTINGS_SERVER_PORT}"
    )
    print("gesture_settings_auto_save_universal.html에서 저장하면 gestures.json이 자동 생성됩니다.")
    return server


def wait_for_gesture_settings():
    last_message = None

    while True:
        try:
            settings = load_gesture_settings()
            print("모든 얼굴 제스처 저장 확인 완료")
            return settings
        except Exception as e:
            message = str(e)
            if message != last_message:
                print("제스처 설정 대기 중:", message)
                print("HTML에서 기본 중립 얼굴과 필요한 제스처를 저장하세요.")
                last_message = message
            time.sleep(1)
