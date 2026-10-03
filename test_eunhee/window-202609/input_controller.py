# input_controller.py

import time

from shortcut_manager import (
    process_key,
    reset_key_state,
    click_current_key
)


class InputController:

    def __init__(self):

        self.current_key = None

        # 클릭 중복 방지
        self.last_click_time = 0

        # 0.3초 안에는 연속 클릭 무시
        self.click_delay = 0.3


    # ==========================
    # 레이저 위치 업데이트
    # ==========================
    def update_hover(self, key):

        self.current_key = key

        if key is None:
            reset_key_state()
        else:
            process_key(key)


    # ==========================
    # 얼굴 좌클릭
    # ==========================
    def left_click(self):

        now = time.time()

        if now - self.last_click_time < self.click_delay:
            return False

        self.last_click_time = now

        click_current_key()
        return True


    # ==========================
    # 얼굴 우클릭(추후 구현)
    # ==========================
    def right_click(self):
        pass


    # ==========================
    # 현재 Hover 키
    # ==========================
    def get_hover_key(self):

        return self.current_key