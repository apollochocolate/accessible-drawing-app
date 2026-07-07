"""
face_features.py
얼굴 인식/제스처 비교 담당.
MediaPipe 결과를 숫자 벡터로 바꾸고, gestures.json에 저장된 벡터와 비교합니다.
"""

import os
import time
import urllib.request

import cv2
import numpy as np
import mediapipe as mp

try:
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
except Exception as e:
    print("MediaPipe를 불러오지 못했습니다. 설치 명령어: pip install mediapipe")
    raise e

from config_combined import (
    MODEL_FILE,
    MODEL_URL,
    RUNTIME_NEUTRAL_SECONDS,
    ACTION_DISPLAY_NAMES,
    GESTURE_DISTANCE_THRESHOLD,
    GESTURE_MARGIN,
    TEST_STABLE_FRAMES,
    MIN_NEUTRAL_CHANGE,
    MIN_SAVED_GESTURE_STRENGTH,
    MIN_CURRENT_GESTURE_STRENGTH,
    STRONG_GESTURE_STRENGTH,
    STRONG_GESTURE_MARGIN,
    SIGNATURE_MIN_FEATURE_CHANGE,
    SIGNATURE_MAX_FEATURES,
    ACTION_COOLDOWN,
)


def ensure_model_file():
    if os.path.exists(MODEL_FILE):
        return
    print("face_landmarker.task 모델 파일이 없어 자동 다운로드를 시도합니다.")
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_FILE)
        print("face_landmarker.task 다운로드 완료")
    except Exception as e:
        raise FileNotFoundError(
            "face_landmarker.task 모델 파일이 없습니다.\n"
            "자동 다운로드에도 실패했습니다.\n"
            "MediaPipe face_landmarker.task 파일을 직접 다운로드해서 Python 파일과 같은 폴더에 넣어주세요.\n"
            f"필요한 위치: {MODEL_FILE}"
        ) from e


def create_face_landmarker():
    ensure_model_file()
    base_options = python.BaseOptions(model_asset_path=MODEL_FILE)
    options = vision.FaceLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=True,
    )
    return vision.FaceLandmarker.create_from_options(options)


def frame_to_face_vector(frame, face_landmarker, timestamp_ms):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    rgb = np.ascontiguousarray(rgb)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = face_landmarker.detect_for_video(mp_image, timestamp_ms)
    return make_face_vector(result)


def make_face_vector(result):
    vector = {}

    # 1) MediaPipe blendshape: 눈 감김, 입 벌림, 미소, 찡그림 등
    if result.face_blendshapes:
        for category in result.face_blendshapes[0]:
            try:
                vector[category.category_name] = float(category.score)
            except Exception:
                pass

    landmarks = result.face_landmarks[0] if result.face_landmarks else None

    if landmarks:
        try:
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

            vector["__head_pitch_nose"] = float((nose.y - eye_y) / face_h)
            vector["__head_pitch_chin"] = float((chin.y - eye_y) / face_h)
            vector["__head_yaw"] = float((nose.x - face_center_x) / face_w)
            vector["__head_roll"] = float((right_eye_outer.y - left_eye_outer.y) / face_w)
            vector["__head_z"] = float((nose.z or 0) / face_h)

            upper_lip = landmarks[13]
            lower_lip = landmarks[14]
            mouth_left = landmarks[61]
            mouth_right = landmarks[291]
            vector["__mouth_open_lm"] = float(abs(lower_lip.y - upper_lip.y) / face_h)
            vector["__mouth_width_lm"] = float(abs(mouth_right.x - mouth_left.x) / face_w)

            l_top = landmarks[159]
            l_bottom = landmarks[145]
            r_top = landmarks[386]
            r_bottom = landmarks[374]
            vector["__left_eye_open_lm"] = float(abs(l_bottom.y - l_top.y) / face_h)
            vector["__right_eye_open_lm"] = float(abs(r_bottom.y - r_top.y) / face_h)

            left_brow = landmarks[105]
            right_brow = landmarks[334]
            vector["__left_brow_raise_lm"] = float(abs(left_eye_outer.y - left_brow.y) / face_h)
            vector["__right_brow_raise_lm"] = float(abs(right_eye_outer.y - right_brow.y) / face_h)
        except Exception:
            pass

    # pose matrix는 JS/Python 차이가 커서 기본 매칭에서는 가중치 0으로 둡니다.
    if result.facial_transformation_matrixes:
        try:
            matrix = result.facial_transformation_matrixes[0]
            data = getattr(matrix, "data", None)
            if data is None:
                flat_data = np.asarray(matrix, dtype=np.float32).reshape(-1)
            else:
                flat_data = np.asarray(data, dtype=np.float32).reshape(-1)
            for i, value in enumerate(flat_data):
                vector[f"__pose_{i}"] = float(value) * 0.05
        except Exception:
            pass

    return vector if vector else None


def feature_weight(key):
    if key.startswith("__pose_") or key == "__head_z":
        return 0.0
    if key.startswith("__head_"):
        return 2.4
    if key.startswith("__eye_"):
        return 3.0
    if key.startswith("__mouth_"):
        return 2.8
    if key.startswith("__left_brow") or key.startswith("__right_brow"):
        return 2.0

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
            result[key] = float(value) * w
        except Exception:
            continue
    return result


def make_signature(target_delta):
    target = normalize_match_vector(target_delta)
    items = [(k, v) for k, v in target.items() if abs(v) >= SIGNATURE_MIN_FEATURE_CHANGE]
    items.sort(key=lambda kv: abs(kv[1]), reverse=True)
    return dict(items[:SIGNATURE_MAX_FEATURES])


def weighted_signature_distance(current_delta, signature):
    if not current_delta or not signature:
        return float("inf")
    current = normalize_match_vector(current_delta)
    total = 0.0
    weight_sum = 0.0
    for key, target_value in signature.items():
        current_value = current.get(key, 0.0)
        w = max(abs(target_value), 0.012)
        diff = current_value - target_value
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
    return (sum(v * v for v in values) / max(len(values), 1)) ** 0.5


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
    keys = set(vector.keys()) | set(neutral.keys())
    return {key: float(vector.get(key, 0.0)) - float(neutral.get(key, 0.0)) for key in keys}


def vector_magnitude(vector):
    if not vector:
        return 0.0
    values = [float(v) for v in vector.values()]
    return (sum(v * v for v in values) / max(len(values), 1)) ** 0.5


def find_gesture(current_delta, settings):
    candidates = []
    neutral_saved = settings.get("neutral", {}).get("vector")

    for action_id, data in settings.items():
        if action_id == "neutral" or not isinstance(data, dict):
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
        preview = frame.copy()
        cv2.putText(
            preview,
            f"Neutral calibration {remain:.1f}s",
            (30, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (0, 255, 255),
            2,
        )
        cv2.imshow("Face Gesture Control", preview)
        cv2.waitKey(1)

        ts = int(time.time() * 1000)
        if ts <= last_ts:
            ts = last_ts + 1
        last_ts = ts

        vector = frame_to_face_vector(frame, face_landmarker, ts)
        if vector:
            samples.append(vector)

    neutral = average_vectors(samples)
    if not neutral:
        print("실행 중립 얼굴 캘리브레이션 실패. HTML 중립 얼굴을 사용합니다.")
        return None, last_ts

    print(f"실행 중립 얼굴 캘리브레이션 완료: {len(samples)} samples")
    return neutral, last_ts


class FaceGestureRecognizer:
    def __init__(self, settings, neutral_vector):
        self.settings = settings
        self.neutral_vector = neutral_vector
        self.last_label = None
        self.stable_count = 0
        self.last_action_time = 0.0

    def reset(self):
        self.last_label = None
        self.stable_count = 0

    def update(self, current_vector, allowed):
        """반환값: (face_text, color_bgr, action_id_or_None)"""
        if not allowed:
            self.reset()
            return "Face gesture OFF", (0, 0, 255), None

        if not current_vector:
            self.reset()
            return "Face not detected", (0, 0, 255), None

        current_delta = vector_delta(current_vector, self.neutral_vector)
        current_match_delta = normalize_match_vector(current_delta)
        neutral_change = vector_magnitude(current_match_delta)

        if not current_match_delta or neutral_change < MIN_NEUTRAL_CHANGE:
            yaw = current_vector.get("__head_yaw", 0.0) - self.neutral_vector.get("__head_yaw", 0.0)
            roll = current_vector.get("__head_roll", 0.0) - self.neutral_vector.get("__head_roll", 0.0)
            pitch = current_vector.get("__head_pitch_nose", 0.0) - self.neutral_vector.get("__head_pitch_nose", 0.0)
            self.reset()
            return f"Neutral n={neutral_change:.3f} yaw={yaw:.3f} roll={roll:.3f} pitch={pitch:.3f}", (255, 255, 255), None

        best, second = find_gesture(current_delta, self.settings)
        if not best:
            self.reset()
            return f"No gesture n={neutral_change:.3f}", (255, 255, 255), None

        margin = (second["distance"] if second else float("inf")) - best["distance"]
        detected_by_distance = (
            best["distance"] <= GESTURE_DISTANCE_THRESHOLD
            and margin >= GESTURE_MARGIN
            and best.get("current_strength", 0.0) >= MIN_CURRENT_GESTURE_STRENGTH
        )
        detected_by_strong_gesture = (
            best.get("current_strength", 0.0) >= STRONG_GESTURE_STRENGTH
            and margin >= STRONG_GESTURE_MARGIN
            and neutral_change >= MIN_NEUTRAL_CHANGE
        )
        detected = detected_by_distance or detected_by_strong_gesture

        if not detected:
            keys_preview = ",".join(best.get("signature_keys", [])[:3])
            self.reset()
            return (
                f"Closest: {best['label']} d={best['distance']:.3f} m={margin:.3f} "
                f"c={best.get('current_strength', 0.0):.3f} n={neutral_change:.3f} [{keys_preview}]",
                (255, 255, 255),
                None,
            )

        if self.last_label == best["id"]:
            self.stable_count += 1
        else:
            self.last_label = best["id"]
            self.stable_count = 1

        if self.stable_count < TEST_STABLE_FRAMES:
            return f"Checking: {best['label']} {self.stable_count}/{TEST_STABLE_FRAMES}", (0, 255, 255), None

        now = time.time()
        action_id = None
        if now - self.last_action_time > ACTION_COOLDOWN:
            action_id = best["id"]
            self.last_action_time = now
            self.reset()

        return f"Detected: {best['label']}", (0, 255, 0), action_id
