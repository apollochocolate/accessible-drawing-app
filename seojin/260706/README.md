# 기능별 분리 구조

이 폴더는 기존 단일 Python 파일을 기능별로 나눈 버전입니다.

## 파일 역할

- `main.py`  
  전체 실행 흐름을 담당합니다. 카메라를 열고 각 모듈을 연결합니다.

- `config.py`  
  카메라 번호, 레이저 기준값, 얼굴 제스처 기준값, 스크롤 양 등을 관리합니다.

- `laser_tracker.py`  
  빨간 레이저 점을 검출하고 화면 좌표로 변환합니다.

- `face_gesture.py`  
  MediaPipe 얼굴 특징 추출, 제스처 비교, 중립 얼굴 캘리브레이션을 담당합니다.

- `gesture_server.py`  
  HTML 설정 화면에서 저장한 제스처 정보를 `gestures.json`으로 저장하고 불러옵니다.

- `mouse_actions.py`  
  클릭, 우클릭, 더블클릭, 스크롤을 실제로 실행합니다.

## 같이 넣어야 하는 파일

아래 파일은 이 폴더와 같은 위치에 두세요.

- `gesture_settings_auto_save.html`
- `gestures.json`
- `face_landmarker.task`

`face_landmarker.task`가 없으면 코드가 자동 다운로드를 시도합니다.

## 실행

```bash
pip install opencv-python numpy pyautogui mediapipe
python main.py
```

## 자주 바꾸는 설정

`config.py`에서 주로 조정하면 됩니다.

```python
LASER_CAMERA_INDEX = 2
FACE_CAMERA_INDEX = 0
SCROLL_AMOUNT = 12
ACTION_COOLDOWN = 1.0
```
