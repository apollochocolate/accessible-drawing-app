# linux-202609 — Linux 실행 안내 (Ubuntu/Debian 기준)

## 1. 시스템 패키지 설치

```bash
sudo apt update
sudo apt install portaudio19-dev fonts-nanum v4l-utils

sudo apt install python3.14-venv
sudo apt install -y python3-dev build-essential linux-libc-dev
```

- `portaudio19-dev`: `PyAudio`(음성 클릭 기능)를 pip으로 빌드하기 위해 필요합니다.
- `fonts-nanum`: 키보드 오버레이의 한글 라벨을 정상적으로 렌더링하기 위해 필요합니다
  (없으면 한글이 네모(tofu)로 표시됩니다).
- `v4l-utils`: 카메라 장치 확인용 `v4l2-ctl` 명령을 제공합니다.

## 2. 한/영 전환 IME 설치 (선택, 하지만 권장)

가상 키보드의 "한/영" 키가 실제로 동작하려면 `ibus-hangul` 또는 `fcitx5-hangul` 중 하나가
설치되어 입력기로 등록되어 있어야 합니다. `keyboard_input.py`는 fcitx5를 먼저 시도하고,
없으면 ibus를 시도합니다.

- fcitx5를 쓰는 경우: `sudo apt install fcitx5 fcitx5-hangul` 후 `fcitx5-configtool`로
  한글 입력기를 등록. `fcitx5-remote -t`가 활성 입력기 on/off를 토글하므로, 한글 입력기가
  fcitx5에 등록된 "첫 번째" 입력기여야 물리 한/영 키와 동일하게 동작합니다.
- ibus를 쓰는 경우: `sudo apt install ibus ibus-hangul` 후 `im-config`로 ibus를 기본 IME로
  설정. 설치 후 `ibus engine` 명령으로 현재 활성 엔진 이름을 확인하고, 한글이 아닐 때 전환할
  대상 엔진 이름이 `keyboard_input.py`의 `IBUS_LATIN_ENGINE` 값(`"xkb:us::eng"`)과 다르면
  실제 환경에 맞게 수정하세요.
- 둘 다 설치/실행 중이 아니면 "한/영" 키를 눌러도 콘솔에 안내 메시지만 출력되고 아무 동작도
  하지 않습니다(원본 Windows 버전에서 다른 OS에 대해 동작하던 방식과 동일한 안전한 fallback).
- IME를 새로 설치/변경한 뒤에는 로그인 세션을 재시작해야 반영됩니다.

## 3. Python 가상환경 및 의존성 설치

```bash
cd linux-202609
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

`mediapipe`는 특정 Python 버전/아키텍처(x86_64 권장)에서만 wheel이 제공되므로, 설치가 실패하면
`python3 --version`을 확인하고 필요시 지원되는 버전으로 가상환경을 다시 만드세요.

## 4. 카메라 인덱스 확인

Windows(DirectShow)와 Linux(V4L2)는 카메라 열거 순서가 다를 수 있습니다. 실행 전에 확인하세요:

VMware에서 카메라를 쓰려면 먼저 VM > Removable Devices에서 해당 웹캠을 게스트에 연결해줘야 /dev/video* 가 나타난다.
(노트북 내장 캠을 사용할 경우 드라이브 에러가 발생하면 카메라를 열어 키면 vmware에서 어디로 인식할지 선택할 수 있다.)

```bash
v4l2-ctl --list-devices
# 또는
ls -l /dev/video*
```

확인한 실제 장치 번호를 `config_combined.py`의 `LASER_CAMERA_INDEX` / `FACE_CAMERA_INDEX`에
반영하세요 (기본값은 원본과 동일하게 각각 1, 0으로 두었습니다).

## 5. 디스플레이 서버(X11/Wayland) 주의사항

마우스/키보드를 전역으로 제어하는 `pyautogui`, `pynput`은 X11(또는 XWayland)이 필요합니다.
대부분의 Ubuntu/GNOME 기본 세션은 XWayland로 호환되지만, 순수 Wayland 전용 설정에서는 전역
마우스 이동/클릭이나 전역 키 리스너가 동작하지 않을 수 있습니다. 문제가 발생하면 로그인 화면에서
"Ubuntu on Xorg"(X11) 세션으로 로그인해서 실행해 보세요.

## 6. 실행

```bash
python3 main.py
```

첫 실행 시 `gestures.json`에 필요한 얼굴 제스처가 모두 저장되어 있어야 합니다. 이 파일은 사람마다
캘리브레이션 값이 다르므로, 원본 값이 그대로 복사되어 있더라도 `gesture_settings_auto_save_universal.html`
(내장 로컬 서버, `127.0.0.1:5000`)로 접속해 본인 얼굴 기준으로 재보정하는 것을 권장합니다.
