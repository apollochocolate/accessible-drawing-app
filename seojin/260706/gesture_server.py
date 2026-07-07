"""HTML 제스처 설정값을 저장하고 불러오는 모듈."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from config import (
    GESTURE_FILE,
    REQUIRED_GESTURE_IDS,
    REQUIRED_GESTURE_LABELS,
    SETTINGS_SERVER_HOST,
    SETTINGS_SERVER_PORT,
)


def load_gesture_settings():
    if not GESTURE_FILE.exists():
        raise FileNotFoundError(
            f"gestures.json 파일이 없습니다. 필요한 위치: {GESTURE_FILE}"
        )

    with GESTURE_FILE.open("r", encoding="utf-8") as f:
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
    with GESTURE_FILE.open("w", encoding="utf-8") as f:
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
        if self.path != "/gestures":
            self._send_json(404, {"status": "not_found"})
            return

        if not GESTURE_FILE.exists():
            self._send_json(200, {"status": "empty", "settings": {}})
            return

        try:
            with GESTURE_FILE.open("r", encoding="utf-8") as f:
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
        # 기본 HTTP 로그를 줄이기 위해 비워둠
        return


def start_gesture_save_server():
    server = ThreadingHTTPServer(
        (SETTINGS_SERVER_HOST, SETTINGS_SERVER_PORT),
        GestureSaveHandler
    )

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print(f"제스처 자동 저장 서버 시작: http://{SETTINGS_SERVER_HOST}:{SETTINGS_SERVER_PORT}")
    print("gesture_settings_auto_save.html에서 저장하면 gestures.json이 자동 생성됩니다.")
    return server


def wait_for_gesture_settings():
    while True:
        try:
            return load_gesture_settings()
        except Exception as e:
            print("제스처 설정 대기 중:", e)
            print("HTML에서 기본 중립 얼굴과 필요한 제스처를 저장하세요. Ctrl+C로 종료할 수 있습니다.")
            time.sleep(2)
