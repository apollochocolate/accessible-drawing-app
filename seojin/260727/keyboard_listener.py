# keyboard_listener.py

from pynput import keyboard
from shortcut_manager import process_click

listener = None

def start_keyboard_listener(controller):

    def on_press(key):

        try:
            # Space → 얼굴 클릭과 동일
            if key == keyboard.Key.space:
                controller.left_click()

            # Enter
            elif key == keyboard.Key.enter:
                process_click("Enter")

            # Backspace
            elif key == keyboard.Key.backspace:
                process_click("Backspace")

            # Tab
            elif key == keyboard.Key.tab:
                process_click("Tab")

            # Esc
            elif key == keyboard.Key.esc:
                process_click("Esc")

        except Exception as e:
            print(e)

    global listener

    listener = keyboard.Listener(on_press=on_press)
    listener.start()