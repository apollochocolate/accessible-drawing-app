import RPi.GPIO as GPIO
import time

# 레이저 발사
LASER_PIN = 18

GPIO.setmode(GPIO.BCM)
GPIO.setup(LASER_PIN, GPIO.OUT)

try:
    print("Laser ON")
    GPIO.output(LASER_PIN, GPIO.HIGH)
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopped")
finally:
    GPIO.cleanup()
