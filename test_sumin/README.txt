실행 순서
1. python -m pip install -r requirements.txt
2. python main.py
3. gesture_settings_auto_save_universal.html을 열고 제스처 저장
4. 터미널에 '모든 제스처 설정이 저장되었습니다.'가 뜨면 HTML 카메라를 닫고 Enter
5. Laser Keyboard 창 하나에서 실행

영역 동작
- y < 250: 키보드 영역
  레이저로 키를 가리키고 얼굴 left click 제스처를 하면 해당 키 입력
- y >= 250: 마우스 영역
  레이저 이동으로 실제 커서 이동
  레이저가 멈춘 뒤 얼굴 제스처로 클릭/우클릭/더블클릭/스크롤

카메라 번호 수정
config_combined.py의 LASER_CAMERA_INDEX, FACE_CAMERA_INDEX 변경
