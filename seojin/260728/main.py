"""
팀 통합 실행 파일 - 종이 키보드 마커 보정 버전.

기존 기능은 유지하면서, 레이저 카메라가 실제 종이 키보드를 볼 때
네 모서리 검은 마커를 기준으로 카메라 좌표를 기존 키보드/마우스 좌표로 변환합니다.

동작
1) 레이저 카메라가 종이 키보드와 네 모서리 마커를 봄
2) 마커 4개를 기준으로 종이 좌표 보정
3) 레이저가 종이 키보드 영역: 키 hover
4) 얼굴 left_single: hover 중인 키 입력
5) 레이저가 종이 마우스 영역: 실제 마우스 이동
6) 얼굴 제스처: 클릭 / 우클릭 / 더블클릭 / 스크롤
7) 화면에는 Face Gesture Control 창과 Laser Keyboard 창을 각각 표시
"""

import time
from collections import deque

import cv2
import numpy as np
import pyautogui

from config_combined import (
    LASER_CAMERA_INDEX,
    FACE_CAMERA_INDEX,
    CAMERA_BACKEND,
    WIN_W,
    WIN_H,
    MOUSE_ZONE_Y,
    MOVE_THRESHOLD,
    STOP_DELAY,
    JUMP_THRESHOLD,
    JUMP_REACQUIRE_FRAMES,
    SMOOTHING_ALPHA,
    MOUSE_DEAD_ZONE,
    FACE_GESTURE_ALWAYS_ON_FOR_TEST,
    USE_PAPER_MARKER_BOARD,
    LASER_DETECT_ONLY_ON_PAPER,
    SHOW_CAMERA_WINDOWS,
    SHOW_DEBUG_OVERLAY,
    TERMINAL_STATUS_INTERVAL,
    BOARD_MARKER_LOST_GRACE_SECONDS,
    USE_LASER_BACKGROUND_FILTER,
    LASER_BACKGROUND_CAPTURE_SECONDS,
)
from keyboard_listener import start_keyboard_listener
from keyboard_layout import KEY_MAP
from renderer import draw_keyboard_overlay
from input_controller import InputController

from gesture_store import start_gesture_save_server, wait_for_gesture_settings
from face_features import (
    create_face_landmarker,
    capture_runtime_neutral,
    frame_to_face_vector,
    FaceGestureRecognizer,
)
from laser_tracker import detect_laser
from mouse_controller import mouse_zone_to_screen, move_mouse_to, execute_mouse_action
from paper_board_mapper import PaperBoardMapper
from stt_voice_click import VoiceController


def get_key_at(x, y):
    for name, (x1, y1, x2, y2) in KEY_MAP.items():
        if x1 <= x <= x2 and y1 <= y <= y2:
            return name
    return None


def open_camera(index, name):
    cap = cv2.VideoCapture(index, CAMERA_BACKEND)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIN_W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WIN_H)

    for _ in range(10):
        cap.read()

    if not cap.isOpened():
        raise RuntimeError(f"{name} 카메라를 열 수 없습니다. 카메라 번호: {index}")
    return cap



def capture_laser_background(cap, seconds=1.2):
    """
    레이저를 끈 상태의 배경을 저장합니다.
    이후 현재 프레임과 이 배경을 비교해서 '새로 생긴 빨간 점'만 레이저로 봅니다.
    """
    print("[레이저] 레이저를 끈 상태로 종이를 그대로 비춰주세요.")
    print(f"[레이저] 배경 저장 중... ({seconds:.1f}초)")

    frames = []
    start = time.time()

    while time.time() - start < seconds:
        ret, frame = cap.read()
        if ret and frame is not None and frame.size > 0:
            frame = cv2.resize(frame, (WIN_W, WIN_H))
            frames.append(frame.astype(np.float32))
        time.sleep(0.02)

    if not frames:
        print("[레이저] 배경 저장 실패: 기존 색상 기준으로만 레이저를 찾습니다.")
        return None

    background = np.mean(frames, axis=0).clip(0, 255).astype(np.uint8)
    background = cv2.GaussianBlur(background, (3, 3), 0)
    print("[레이저] 배경 저장 완료. 이제 레이저를 켜고 사용하세요.")
    return background


def put_status(frame, text, y, color=(255, 255, 255)):
    if not SHOW_DEBUG_OVERLAY:
        return
    cv2.putText(
        frame,
        text,
        (10, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        color,
        2,
    )


CLICK_NAME = {
    "left_single": "왼쪽 클릭",
    "right_single": "오른쪽 클릭",
    "left_double": "더블클릭",
    "scroll_up": "스크롤 위",
    "scroll_down": "스크롤 아래",
}


class TerminalEventLogger:
    """터미널에 실시간 상태를 계속 뿌리지 않고, 의미 있는 변화만 출력합니다."""

    def __init__(self):
        self.last_board_ready = None
        self.last_board_success_time = None
        self.board_lost_grace_seconds = BOARD_MARKER_LOST_GRACE_SECONDS
        self.last_zone = None
        self.pending_zone = None
        self.pending_zone_count = 0
        self.zone_confirm_frames = 3

    def log(self, message):
        print(message, flush=True)

    def face_start(self):
        self.log("[얼굴] 얼굴 인식 시작!")

    def face_ready(self):
        self.log("[얼굴] 얼굴 인식 준비 완료")

    def update_board(self, board_ready):
        """
        마커 인식 로그를 안정화합니다.
        카메라가 1~2프레임 정도 마커를 놓쳐도 바로 '끊김'으로 보지 않고,
        마지막 정상 인식 후 일정 시간 동안은 인식된 상태로 유지합니다.
        반환값은 실제 로직에서 사용할 안정화된 board_ready 값입니다.
        """
        now = time.time()

        if board_ready:
            self.last_board_success_time = now
            if self.last_board_ready is not True:
                self.last_board_ready = True
                self.log("[종이] 네 모서리 마커 인식 완료")
            return True

        # 처음부터 아직 한 번도 못 잡은 상태
        if self.last_board_ready is None:
            self.last_board_ready = False
            self.log("[종이] 네 모서리 마커 인식 대기 중...")
            return False

        # 이미 인식된 상태라면 잠깐 놓친 것은 무시
        if self.last_board_ready is True:
            if (
                self.last_board_success_time is not None
                and now - self.last_board_success_time <= self.board_lost_grace_seconds
            ):
                return True

            self.last_board_ready = False
            self.log("[종이] 네 모서리 마커 인식 끊김")
            return False

        return False

    def update_zone(self, zone):
        if zone == "keyboard":
            normalized = "keyboard"
        elif zone == "mouse":
            normalized = "mouse"
        else:
            normalized = "none"

        if normalized != self.pending_zone:
            self.pending_zone = normalized
            self.pending_zone_count = 1
            return

        self.pending_zone_count += 1
        if normalized == self.last_zone or self.pending_zone_count < self.zone_confirm_frames:
            return

        previous = self.last_zone
        self.last_zone = normalized

        if normalized == "keyboard":
            self.log("[영역] 키보드 영역으로 변경")
        elif normalized == "mouse":
            self.log("[영역] 마우스 영역으로 변경")
        elif previous in ("keyboard", "mouse"):
            self.log("[영역] 입력 영역 밖 또는 레이저 없음")

    def keyboard_input(self, key, action_id, source="face"):
        source_name = "음성" if source == "voice" else "얼굴"
        click_name = CLICK_NAME.get(action_id, action_id)
        self.log(f"[키보드] {key} 버튼 입력 ({source_name} {click_name})")

    def mouse_input(self, action_id, source="face"):
        source_name = "음성" if source == "voice" else "얼굴"
        click_name = CLICK_NAME.get(action_id, action_id)
        self.log(f"[마우스] {click_name} 실행 ({source_name})")


def route_face_action(action_id, zone, controller, voice_controller=None, source="face", event_logger=None):
    """얼굴/음성 제스처 결과를 현재 영역에 맞게 전달합니다."""
    if not action_id:
        return

    hover_key = controller.get_hover_key()

    # 키보드 영역에서는 left_single과 left_double을 모두 "키 선택"으로 처리합니다.
    # 즉 키보드 위에서 더블클릭 제스처를 해도 해당 키를 1번만 입력합니다.
    keyboard_select_actions = {"left_single", "left_double"}

    # 키보드 영역에서 음성 버튼을 얼굴 클릭/더블클릭으로 누르면 STT를 켜고 끕니다.
    # 음성 명령으로 '클릭'을 말했을 때 음성 버튼이 다시 눌려 꺼지는 것은 막습니다.
    if zone == "keyboard" and action_id in keyboard_select_actions and hover_key in ["Voice", "음성"]:
        if event_logger is not None:
            event_logger.keyboard_input(hover_key, action_id, source=source)
        if source == "face" and voice_controller is not None:
            voice_controller.toggle()
        return

    # 키보드 영역에서는 클릭/더블클릭 제스처 모두 현재 hover 키 입력으로 사용합니다.
    if zone == "keyboard":
        if action_id in keyboard_select_actions and hover_key:
            clicked = controller.left_click()
            if clicked and event_logger is not None:
                event_logger.keyboard_input(hover_key, action_id, source=source)
        return

    # 마우스 영역 또는 레이저가 없는 상태에서는 마우스 동작 실행
    if event_logger is not None:
        event_logger.mouse_input(action_id, source=source)
    execute_mouse_action(action_id)


def main():
    # v13과 같은 흐름: 제스처 저장 확인 → Enter → 카메라 실행
    settings = wait_for_gesture_settings()

    print()
    print("모든 제스처 설정이 저장되었습니다.")
    print("브라우저의 얼굴 설정 화면을 닫거나 카메라 사용을 멈춘 뒤 Enter를 누르세요.")
    input("준비되면 Enter: ")

    print("[얼굴] 얼굴 인식 시작!")
    face_landmarker = create_face_landmarker()

    print(f"레이저 카메라: {LASER_CAMERA_INDEX}")
    print(f"얼굴 카메라: {FACE_CAMERA_INDEX}")
    print(f"종이 마커 보정 사용: {USE_PAPER_MARKER_BOARD}")

    laser_cap = open_camera(LASER_CAMERA_INDEX, "레이저")
    face_cap = open_camera(FACE_CAMERA_INDEX, "얼굴")

    laser_background = None
    if USE_LASER_BACKGROUND_FILTER:
        laser_background = capture_laser_background(
            laser_cap,
            seconds=LASER_BACKGROUND_CAPTURE_SECONDS,
        )

    runtime_neutral, last_face_timestamp_ms = capture_runtime_neutral(
        face_cap,
        face_landmarker,
    )
    neutral_vector = runtime_neutral or settings["neutral"]["vector"]
    face_recognizer = FaceGestureRecognizer(settings, neutral_vector)
    print("[얼굴] 얼굴 인식 준비 완료")

    controller = InputController()
    start_keyboard_listener(controller)

    event_logger = TerminalEventLogger()

    # 음성 버튼이 켜진 뒤, 음성 명령도 얼굴 제스처와 같은 분배 로직을 사용합니다.
    runtime_state = {"zone": "none"}
    voice_controller = VoiceController(
        lambda action_id: route_face_action(
            action_id,
            runtime_state.get("zone", "none"),
            controller,
            voice_controller=None,
            source="voice",
            event_logger=event_logger,
        )
    )

    board_mapper = PaperBoardMapper() if USE_PAPER_MARKER_BOARD else None

    raw_x_history = deque(maxlen=5)
    raw_y_history = deque(maxlen=5)

    last_laser_x = None
    last_laser_y = None
    last_valid_raw_x = None
    last_valid_raw_y = None
    jump_reject_count = 0

    smoothed_screen_x = None
    smoothed_screen_y = None
    last_move_time = time.time()

    current_zone = "none"
    detected_key = None
    face_text = "Face ready"
    face_color = (255, 255, 255)
    last_terminal_status_time = 0.0

    print("실행 중...")
    if USE_PAPER_MARKER_BOARD:
        print("종이 네 모서리 검은 마커 4개를 레이저 카메라 화면 안에 모두 보이게 해주세요.")
        print("종이 키보드 영역: 키보드 hover")
        print("종이 MOUSE AREA 아래: 마우스 이동")
    else:
        print("구분선 위: 키보드 영역")
        print("구분선 아래: 마우스 영역")
    print("키보드 영역 + 얼굴 left click: 현재 글자 입력")
    print("마우스 영역 + 얼굴 제스처: 클릭/우클릭/더블클릭/스크롤")
    print("음성 버튼 + 얼굴 left click: 음성 제어 ON/OFF")
    print("음성 명령어: 클릭 / 우클릭 / 더블클릭 / 스크롤 위 / 스크롤 아래 / 음성 종료")
    if SHOW_CAMERA_WINDOWS:
        print("q 또는 ESC: 종료")
    else:
        print("카메라 창 표시 OFF: 터미널에는 이벤트만 출력합니다.")
        print("종료하려면 Ctrl+C를 누르세요.")

    try:
        while True:
            # ==================================================
            # 1. 레이저 카메라: 종이 마커/레이저 처리
            # ==================================================
            ret_laser, frame = laser_cap.read()
            if not ret_laser or frame is None or frame.size == 0:
                frame = np.zeros((WIN_H, WIN_W, 3), dtype=np.uint8)

            frame = cv2.resize(frame, (WIN_W, WIN_H))

            board_ready = True
            if board_mapper is not None:
                raw_board_ready = board_mapper.update(frame)
                # raw_board_ready는 1~2프레임씩 흔들릴 수 있으므로,
                # 터미널 로그와 실제 로직에는 안정화된 board_ready를 사용합니다.
                board_ready = event_logger.update_board(raw_board_ready)

            # 종이 마커가 잡힌 뒤에는 종이 내부에서만 레이저를 찾습니다.
            # 주변 모니터/아이콘/반사광의 빨간 점을 레이저로 오인식하는 것을 줄입니다.
            allowed_laser_mask = None
            if (
                board_mapper is not None
                and board_ready
                and LASER_DETECT_ONLY_ON_PAPER
            ):
                allowed_laser_mask = board_mapper.get_paper_mask(frame.shape)

            if board_mapper is not None and not board_ready and LASER_DETECT_ONLY_ON_PAPER:
                candidate = None
            else:
                candidate = detect_laser(
                    frame,
                    prefer_point=(last_valid_raw_x, last_valid_raw_y),
                    allowed_mask=allowed_laser_mask,
                    background_frame=laser_background,
                )

            laser_detected = candidate is not None
            detected_key = None
            current_zone = "none"

            if candidate is not None:
                raw_x_history.append(candidate["x"])
                raw_y_history.append(candidate["y"])
                raw_x = int(np.median(raw_x_history))
                raw_y = int(np.median(raw_y_history))

                accept_position = True
                if last_valid_raw_x is not None and last_valid_raw_y is not None:
                    jump = (
                        (raw_x - last_valid_raw_x) ** 2
                        + (raw_y - last_valid_raw_y) ** 2
                    ) ** 0.5

                    if jump > JUMP_THRESHOLD:
                        jump_reject_count += 1
                        if jump_reject_count < JUMP_REACQUIRE_FRAMES:
                            accept_position = False
                        else:
                            # 새 위치에 계속 레이저가 있으면 재획득
                            last_valid_raw_x = raw_x
                            last_valid_raw_y = raw_y
                            jump_reject_count = 0
                    else:
                        last_valid_raw_x = raw_x
                        last_valid_raw_y = raw_y
                        jump_reject_count = 0
                else:
                    last_valid_raw_x = raw_x
                    last_valid_raw_y = raw_y

                if accept_position:
                    if SHOW_DEBUG_OVERLAY:
                        cv2.circle(frame, (raw_x, raw_y), 8, (0, 0, 255), -1)
                        cv2.circle(frame, (raw_x, raw_y), 12, (255, 255, 255), 2)

                    # ------------------------------------------
                    # 종이 마커 보정: 카메라 좌표 → 기존 가상 좌표
                    # ------------------------------------------
                    if board_mapper is not None:
                        if not board_ready:
                            controller.update_hover(None)
                            put_status(frame, "Paper markers not detected", 25, (0, 0, 255))
                            virtual_x = None
                            virtual_y = None
                            mapped_zone = "outside"
                        else:
                            mapped = board_mapper.camera_to_virtual(raw_x, raw_y)
                            mapped_zone = mapped.get("zone", "outside")
                            virtual_x = mapped.get("x")
                            virtual_y = mapped.get("y")

                            px = mapped.get("paper_x", 0.0)
                            py = mapped.get("paper_y", 0.0)
                            put_status(
                                frame,
                                f"PAPER ({px:.0f}, {py:.0f}) -> {mapped_zone}",
                                25,
                                (0, 255, 255) if mapped_zone != "outside" else (0, 0, 255),
                            )
                    else:
                        virtual_x = float(raw_x)
                        virtual_y = float(raw_y)
                        mapped_zone = "keyboard" if virtual_y < MOUSE_ZONE_Y else "mouse"

                    if virtual_x is not None and virtual_y is not None:
                        laser_x = int(virtual_x)
                        laser_y = int(virtual_y)

                        # ------------------------------------------
                        # 키보드 영역: 친구 키보드 로직 유지
                        # ------------------------------------------
                        if mapped_zone == "keyboard" or laser_y < MOUSE_ZONE_Y:
                            detected_key = get_key_at(laser_x, laser_y)

                            smoothed_screen_x = None
                            smoothed_screen_y = None
                            last_laser_x = None
                            last_laser_y = None

                            if detected_key:
                                current_zone = "keyboard"
                                controller.update_hover(detected_key)
                                put_status(frame, f"KEYBOARD: {detected_key}", 55, (0, 255, 0))
                            else:
                                # 종이 키보드 박스 안이라도 실제 키 사각형 위가 아니면 키보드 입력으로 보지 않습니다.
                                # 이렇게 해야 키 사이 빈칸/키보드 아래 여백에서 임의 키가 눌리는 것을 막을 수 있습니다.
                                current_zone = "outside"
                                controller.update_hover(None)
                                put_status(frame, "KEYBOARD GAP / NO KEY", 55, (0, 0, 255))

                        # ------------------------------------------
                        # 마우스 영역: 기존 레이저 마우스 로직
                        # ------------------------------------------
                        elif mapped_zone == "mouse" or laser_y >= MOUSE_ZONE_Y:
                            current_zone = "mouse"
                            controller.update_hover(None)

                            if last_laser_x is not None and last_laser_y is not None:
                                diff = (
                                    (laser_x - last_laser_x) ** 2
                                    + (laser_y - last_laser_y) ** 2
                                ) ** 0.5
                                if diff > MOVE_THRESHOLD:
                                    last_move_time = time.time()
                            else:
                                last_move_time = time.time()

                            last_laser_x = laser_x
                            last_laser_y = laser_y

                            screen_x, screen_y = mouse_zone_to_screen(laser_x, laser_y)

                            if smoothed_screen_x is None or smoothed_screen_y is None:
                                smoothed_screen_x = screen_x
                                smoothed_screen_y = screen_y
                            else:
                                smoothed_screen_x = int(
                                    smoothed_screen_x * (1 - SMOOTHING_ALPHA)
                                    + screen_x * SMOOTHING_ALPHA
                                )
                                smoothed_screen_y = int(
                                    smoothed_screen_y * (1 - SMOOTHING_ALPHA)
                                    + screen_y * SMOOTHING_ALPHA
                                )

                            current_mouse_x, current_mouse_y = pyautogui.position()
                            mouse_diff = (
                                (smoothed_screen_x - current_mouse_x) ** 2
                                + (smoothed_screen_y - current_mouse_y) ** 2
                            ) ** 0.5

                            if mouse_diff > MOUSE_DEAD_ZONE:
                                move_mouse_to(smoothed_screen_x, smoothed_screen_y)

                            put_status(frame, "MOUSE AREA", 55, (0, 255, 255))

                    else:
                        controller.update_hover(None)
                        smoothed_screen_x = None
                        smoothed_screen_y = None
                        put_status(frame, "Laser outside paper active area", 55, (0, 0, 255))

                    if SHOW_DEBUG_OVERLAY:
                        cv2.putText(
                            frame,
                            f"Laser raw ({raw_x}, {raw_y}) {candidate.get('mode', '')} score={candidate.get('score', 0):.0f}",
                            (raw_x + 15, max(raw_y - 15, 15)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.55,
                            (0, 255, 0),
                            2,
                        )
                else:
                    controller.update_hover(None)
                    put_status(frame, "Laser position checking", 25, (0, 0, 255))

            else:
                raw_x_history.clear()
                raw_y_history.clear()
                last_laser_x = None
                last_laser_y = None
                last_valid_raw_x = None
                last_valid_raw_y = None
                jump_reject_count = 0
                smoothed_screen_x = None
                smoothed_screen_y = None
                controller.update_hover(None)
                put_status(frame, "Laser not detected", 25, (0, 0, 255))

            # ==================================================
            # 2. 얼굴 제스처 허용 조건
            # ==================================================
            stopped_time = time.time() - last_move_time

            if FACE_GESTURE_ALWAYS_ON_FOR_TEST:
                face_allowed = True
            elif current_zone == "keyboard":
                # 키보드에서는 레이저로 키를 가리킨 채 얼굴 클릭해야 하므로 항상 ON
                face_allowed = True
            elif current_zone == "mouse":
                # 마우스 이동 중에는 OFF, 멈춘 뒤 ON
                face_allowed = stopped_time > STOP_DELAY
            else:
                # 레이저가 없으면 현재 커서 위치에 얼굴 제스처 사용 가능
                face_allowed = True

            runtime_state["zone"] = current_zone
            event_logger.update_zone(current_zone)

            # ==================================================
            # 3. 얼굴 카메라: 얼굴 제스처 처리 + 별도 얼굴 창 표시
            # ==================================================
            ret_face, face_frame = face_cap.read()
            if ret_face:
                timestamp_ms = int(time.time() * 1000)
                if timestamp_ms <= last_face_timestamp_ms:
                    timestamp_ms = last_face_timestamp_ms + 1
                last_face_timestamp_ms = timestamp_ms

                current_vector = frame_to_face_vector(
                    face_frame,
                    face_landmarker,
                    timestamp_ms,
                )
                face_text, face_color, action_id = face_recognizer.update(
                    current_vector,
                    face_allowed,
                )

                route_face_action(action_id, current_zone, controller, voice_controller, source="face", event_logger=event_logger)

                # 얼굴 인식 상태는 옵션이 켜져 있을 때만 화면에 표시
                if SHOW_CAMERA_WINDOWS:
                    if SHOW_DEBUG_OVERLAY:
                        cv2.putText(
                            face_frame,
                            face_text,
                            (30, 40),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.75,
                            face_color,
                            2,
                        )
                        cv2.putText(
                            face_frame,
                            voice_controller.last_message,
                            (30, 75),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.65,
                            (0, 255, 255) if voice_controller.is_running else (255, 255, 255),
                            2,
                        )
                    cv2.imshow("Face Gesture Control", face_frame)
            else:
                face_text = "Face camera frame error"
                face_color = (0, 0, 255)

            # ==================================================
            # 4. 화면 표시 또는 터미널 상태 출력
            # ==================================================
            if SHOW_CAMERA_WINDOWS:
                if SHOW_DEBUG_OVERLAY:
                    if board_mapper is not None:
                        # 종이 모드에서는 실제 종이에 hover된 키만 투영해서 표시합니다.
                        board_mapper.draw_debug(frame, detected_key, KEY_MAP)
                    else:
                        # 기존 모드에서는 고정 오버레이 표시
                        draw_keyboard_overlay(frame, KEY_MAP, detected_key)

                    put_status(
                        frame,
                        voice_controller.last_message,
                        85,
                        (0, 255, 255) if voice_controller.is_running else (255, 255, 255),
                    )

                cv2.imshow("Laser Keyboard", frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q") or key == 27:
                    break
            else:
                # 터미널 전용 모드에서는 상태를 계속 출력하지 않습니다.
                # 의미 있는 이벤트는 TerminalEventLogger가 변화가 생겼을 때만 출력합니다.
                time.sleep(0.001)

    finally:
        try:
            voice_controller.stop()
        except Exception:
            pass
        laser_cap.release()
        face_cap.release()
        cv2.destroyAllWindows()
        print("카메라가 꺼졌습니다.")


if __name__ == "__main__":
    start_gesture_save_server()
    main()
