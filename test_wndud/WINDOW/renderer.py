# mode_manager.py

laser_only_mode = False
mode_hover_lock = False



def process_mode_key(detected_key):

    global laser_only_mode
    global mode_hover_lock

    
    if detected_key != "Mode":
        mode_hover_lock = False
        return

 
    if mode_hover_lock:
        return

    mode_hover_lock = True

    laser_only_mode = not laser_only_mode

    print(
        f"[MODE] "
        f"{'LASER ONLY' if laser_only_mode else 'KEYBOARD MODE'}"
    )


def is_laser_only_mode():
    return laser_only_mode