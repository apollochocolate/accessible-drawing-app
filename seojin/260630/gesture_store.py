"""
gesture_store.py
얼굴 제스처 설정 저장/불러오기 담당.

흐름은 예전에 만든 v13 방식과 동일합니다.
1) Python을 먼저 실행하면 저장 서버만 켜짐
2) HTML에서 제스처를 저장하면 gestures.json 생성
3) 모든 제스처가 저장되면 main에서 Enter를 기다림
4) Enter 후 카메라 실행
"""

import json
import os
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from config_combined import (
    BASE_DIR,
    GESTURE_FILE,
    SETTINGS_SERVER_HOST,
    SETTINGS_SERVER_PORT,
    REQUIRED_GESTURE_IDS,
    REQUIRED_GESTURE_LABELS,
)

HTML_FILE = os.path.join(BASE_DIR, "gesture_settings_auto_save_universal.html")


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


def _read_html():
    if not os.path.exists(HTML_FILE):
        return None
    with open(HTML_FILE, "rb") as f:
        return f.read()


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

    def _send_html(self, status_code, html_bytes):
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(html_bytes)))
        self.end_headers()
        self.wfile.write(html_bytes)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        # 파일을 직접 열어도 되지만, 필요하면 이 주소로 열 수도 있음.
        # http://127.0.0.1:5000/settings
        if self.path in ["/", "/settings", "/gesture_settings_auto_save_universal.html"]:
            html = _read_html()
            if html is None:
                self._send_json(404, {
                    "status": "html_not_found",
                    "message": f"HTML 파일이 없습니다: {HTML_FILE}",
                })
                return
            self._send_html(200, html)
            return

        if self.path == "/health":
            self._send_json(200, {"status": "ok", "gesture_file": GESTURE_FILE})
            return

        if self.path != "/gestures":
            self._send_json(404, {"status": "not_found"})
            return

        if not os.path.exists(GESTURE_FILE):
            self._send_json(200, {"status": "empty", "settings": {}, "gesture_file": GESTURE_FILE})
            return

        try:
            with open(GESTURE_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
            self._send_json(200, {"status": "ok", "settings": settings, "gesture_file": GESTURE_FILE})
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
    server = ThreadingHTTPServer((SETTINGS_SERVER_HOST, SETTINGS_SERVER_PORT), GestureSaveHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print(f"제스처 자동 저장 서버 시작: http://{SETTINGS_SERVER_HOST}:{SETTINGS_SERVER_PORT}")
    print("브라우저에서 저장하면 gestures.json이 자동 생성됩니다.")
    print(f"설정 화면 주소: http://{SETTINGS_SERVER_HOST}:{SETTINGS_SERVER_PORT}/settings")
    print(f"저장 위치: {GESTURE_FILE}")
    return server


def wait_for_gesture_settings():
    while True:
        try:
            return load_gesture_settings()
        except Exception as e:
            print("제스처 설정 대기 중:", e)
            print("HTML에서 기본 중립 얼굴과 필요한 제스처를 저장하세요. Ctrl+C로 종료할 수 있습니다.")
            time.sleep(2)
