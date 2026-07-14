"""MediaPipe 얼굴 특징 추출, 제스처 비교, 중립 얼굴 캘리브레이션."""

import time
import urllib.request

import cv2
import mediapipe as mp
import numpy as np

try:
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
except Exception as exc:
    print("MediaPipe를 불러오지 못했습니다.")
    print("설치 명령어: pip install mediapipe")
    raise exc

from config import (
    ACTION_DISPLAY_NAMES,
    MIN_SAVED_GESTURE_STRENGTH,
    MODEL_FILE,
    MODEL_URL,
    RUNTIME_NEUTRAL_SECONDS,
    SIGNATURE_MAX_FEATURES,
    SIGNATURE_MIN_FEATURE_CHANGE,
)

def ensure_model_file():
    if MODEL_FILE.exists():
        return

    print("face_landmarker.task 모델 파일이 없어 자동 다운로드를 시도합니다.")

    try:
        urllib.request.urlretrieve(MODEL_URL, str(MODEL_FILE))
        print("face_landmarker.task 다운로드 완료")
    except Exception as e:
        raise FileNotFoundError(
            f"face_landmarker.task 모델 파일이 없습니다.\n"
            f"자동 다운로드에도 실패했습니다.\n"
            f"MediaPipe face_landmarker.task 파일을 직접 다운로드해서 이 Python 파일과 같은 폴더에 넣어주세요.\n"
            f"필요한 위치: {MODEL_FILE}"
        ) from e


def create_face_landmarker():
    ensure_model_file()

    base_options = python.BaseOptions(model_asset_path=str(MODEL_FILE))

    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=False,
    )

    return vision.FaceLandmarker.create_from_options(options)


def make_face_vector(result):
    """
    얼굴 인식 결과를 숫자 벡터로 바꿉니다.
    v12 핵심:
    - 표정 blendshape 전체
    - 고개 좌우 회전 yaw
    - 고개 좌우 기울임 roll
    - 고개 위/아래 pitch
    - 입 벌림/입 너비
    - 양쪽 눈 감김 정도
    - 눈썹 움직임
    을 모두 저장/비교합니다.
    """
    vector = {}

    # 1) MediaPipe blendshape 점수: 눈 감김, 입 벌림, 미소, 찡그림 등
    if result.face_blendshapes:
        for category in result.face_blendshapes[0]:
            try:
                vector[category.category_name] = float(category.score)
            except Exception:
                pass

    landmarks = result.face_landmarks[0] if result.face_landmarks else None

    if landmarks:
        try:
            # 주요 랜드마크
            nose = landmarks[1]
            forehead = landmarks[10]
            chin = landmarks[152]
            left_eye_outer = landmarks[33]
            right_eye_outer = landmarks[263]
            left_cheek = landmarks[234]
            right_cheek = landmarks[454]

            face_w = max(abs(right_cheek.x - left_cheek.x), 0.001)
            face_h = max(abs(chin.y - forehead.y), 0.001)
            eye_y = (left_eye_outer.y + right_eye_outer.y) / 2
            face_center_x = (left_cheek.x + right_cheek.x) / 2

            # 고개 숙임/듦, 좌우 돌림, 좌우 기울임
            vector["__head_pitch_nose"] = float((nose.y - eye_y) / face_h)
            vector["__head_pitch_chin"] = float((chin.y - eye_y) / face_h)
            vector["__head_yaw"] = float((nose.x - face_center_x) / face_w)
            vector["__head_roll"] = float((right_eye_outer.y - left_eye_outer.y) / face_w)

            # 입 벌림/입 너비. 13/14는 위아래 입술, 61/291은 입꼬리 쪽.
            upper_lip = landmarks[13]
            lower_lip = landmarks[14]
            mouth_left = landmarks[61]
            mouth_right = landmarks[291]
            vector["__mouth_open_lm"] = float(abs(lower_lip.y - upper_lip.y) / face_h)
            vector["__mouth_width_lm"] = float(abs(mouth_right.x - mouth_left.x) / face_w)

            # 눈 열림 정도. 값이 작아지면 눈을 감은 것.
            l_top = landmarks[159]
            l_bottom = landmarks[145]
            r_top = landmarks[386]
            r_bottom = landmarks[374]
            vector["__left_eye_open_lm"] = float(abs(l_bottom.y - l_top.y) / face_h)
            vector["__right_eye_open_lm"] = float(abs(r_bottom.y - r_top.y) / face_h)

            # 눈썹 움직임. 값이 커지면 눈썹/이마 쪽 움직임이 커진 것.
            left_brow = landmarks[105]
            right_brow = landmarks[334]
            vector["__left_brow_raise_lm"] = float(abs(left_eye_outer.y - left_brow.y) / face_h)
            vector["__right_brow_raise_lm"] = float(abs(right_eye_outer.y - right_brow.y) / face_h)
        except Exception:
            pass


    return vector if vector else None


def feature_weight(key):
    """특징별 가중치. 고개/눈/입 움직임은 blendshape보다 조금 더 강하게 봅니다."""
    if key.startswith("__head_"):
        return 2.4
    if key.startswith("__eye_"):
        return 3.0
    if key.startswith("__mouth_"):
        return 2.8
    if key.startswith("__left_brow") or key.startswith("__right_brow"):
        return 2.0
    # blendshape 중에서도 눈/입/턱 계열은 중요하게 봄
    lower = key.lower()
    if "eye" in lower or "blink" in lower:
        return 2.3
    if "mouth" in lower or "jaw" in lower or "lip" in lower:
        return 2.2
    if "brow" in lower:
        return 1.8
    return 1.0


def normalize_match_vector(vector):
    if not vector:
        return {}

    result = {}
    for key, value in vector.items():
        w = feature_weight(key)
        if w <= 0:
            continue
        try:
            v = float(value)
        except Exception:
            continue
        result[key] = v * w
    return result


def make_signature(target_delta):
    """
    저장된 제스처에서 실제로 많이 변한 특징만 뽑습니다.
    예: 고개를 왼쪽으로 내리는 제스처면 head_roll/head_pitch가 주요 특징이 됨.
    예: 입 벌리기면 jawOpen/mouth_open이 주요 특징이 됨.
    """
    target = normalize_match_vector(target_delta)
    items = [(k, v) for k, v in target.items() if abs(v) >= SIGNATURE_MIN_FEATURE_CHANGE]
    items.sort(key=lambda kv: abs(kv[1]), reverse=True)
    items = items[:SIGNATURE_MAX_FEATURES]
    return dict(items)


def weighted_signature_distance(current_delta, signature):
    if not current_delta or not signature:
        return float("inf")

    current = normalize_match_vector(current_delta)
    total = 0.0
    weight_sum = 0.0

    for key, target_value in signature.items():
        current_value = current.get(key, 0.0)
        # 많이 변한 특징일수록 더 중요하게 비교
        w = max(abs(target_value), 0.012)
        diff = current_value - target_value

        # 방향이 완전히 반대면 강한 패널티. 왼쪽/오른쪽, 위/아래 구분에 중요함.
        if abs(target_value) >= SIGNATURE_MIN_FEATURE_CHANGE and current_value * target_value < 0:
            diff *= 1.8

        total += w * diff * diff
        weight_sum += w

    return (total / max(weight_sum, 1e-9)) ** 0.5


def vector_strength_on_signature(current_delta, signature):
    current = normalize_match_vector(current_delta)
    if not current or not signature:
        return 0.0
    values = [current.get(k, 0.0) for k in signature.keys()]
    if not values:
        return 0.0
    return (sum(v * v for v in values) / len(values)) ** 0.5


def average_vectors(vectors):
    if not vectors:
        return None

    avg = {}
    count = {}
    for vector in vectors:
        for key, value in vector.items():
            try:
                value = float(value)
            except Exception:
                continue
            avg[key] = avg.get(key, 0.0) + value
            count[key] = count.get(key, 0) + 1

    for key in list(avg.keys()):
        avg[key] /= max(count.get(key, 1), 1)

    return avg


def vector_delta(vector, neutral):
    if not vector or not neutral:
        return None

    result = {}
    keys = set(vector.keys()) | set(neutral.keys())

    for key in keys:
        result[key] = float(vector.get(key, 0.0)) - float(neutral.get(key, 0.0))

    return result


def vector_magnitude(vector):
    if not vector:
        return 0.0
    values = [float(v) for v in vector.values()]
    if not values:
        return 0.0
    return (sum(v * v for v in values) / len(values)) ** 0.5


def find_gesture(current_delta, settings):
    """
    v12: 모든 동작을 저장된 얼굴 변화 패턴으로 비교합니다.
    특정 동작을 고개 기울임/돌림으로 하드코딩하지 않습니다.
    """
    candidates = []
    neutral_saved = settings.get("neutral", {}).get("vector")

    for action_id, data in settings.items():
        if action_id == "neutral":
            continue
        if not isinstance(data, dict):
            continue

        target_raw = data.get("delta")
        if not target_raw and data.get("vector") and neutral_saved:
            target_raw = vector_delta(data.get("vector"), neutral_saved)
        if not target_raw:
            continue

        signature = make_signature(target_raw)
        if not signature:
            continue

        target_strength = vector_magnitude(signature)
        if target_strength < MIN_SAVED_GESTURE_STRENGTH:
            continue

        dist = weighted_signature_distance(current_delta, signature)
        current_strength = vector_strength_on_signature(current_delta, signature)

        candidates.append({
            "id": action_id,
            "label": ACTION_DISPLAY_NAMES.get(action_id, action_id),
            "distance": dist,
            "strength": target_strength,
            "current_strength": current_strength,
            "signature_keys": list(signature.keys()),
        })

    candidates.sort(key=lambda item: item["distance"])
    best = candidates[0] if len(candidates) >= 1 else None
    second = candidates[1] if len(candidates) >= 2 else None
    return best, second


def capture_runtime_neutral(face_cap, face_landmarker):
    print("Python 얼굴 카메라 기준 중립 얼굴을 다시 캘리브레이션합니다.")
    print("2초 동안 가만히 정면을 봐주세요.")

    samples = []
    last_ts = 0
    start = time.time()

    while time.time() - start < RUNTIME_NEUTRAL_SECONDS:
        ret, frame = face_cap.read()
        if not ret:
            continue

        remain = max(0.0, RUNTIME_NEUTRAL_SECONDS - (time.time() - start))
        cv2.putText(
            frame,
            f"Neutral calibration {remain:.1f}s",
            (30, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 255),
            2
        )
        cv2.imshow("Face Gesture Control", frame)
        cv2.waitKey(1)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb = np.ascontiguousarray(rgb)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        ts = int(time.time() * 1000)
        if ts <= last_ts:
            ts = last_ts + 1
        last_ts = ts

        result = face_landmarker.detect_for_video(mp_image, ts)
        vector = make_face_vector(result)
        if vector:
            samples.append(vector)

    neutral = average_vectors(samples)
    if not neutral:
        print("실행 중립 얼굴 캘리브레이션 실패. HTML 중립 얼굴을 사용합니다.")
        return None, last_ts

    print(f"실행 중립 얼굴 캘리브레이션 완료: {len(samples)} samples")
    return neutral, last_ts