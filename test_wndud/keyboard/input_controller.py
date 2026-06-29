# input_controller.py

from shortcut_manager import (
    process_key,
    reset_key_state,
    click_current_key
)


class InputController:

    def __init__(self):

        self.current_key = None

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

        click_current_key()

    # ==========================
    # 얼굴 우클릭(추후 구현)
    # ==========================
    def right_click(self):

        pass

    # ==========================
    # 현재 키 반환
    # ==========================
    def get_hover_key(self):

        return self.current_key