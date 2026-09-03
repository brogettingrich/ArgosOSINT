"""
Face similarity engine for the "Find With Face" feature.

Ported from face_experiment_DELETE_ME/face_match.py after validation there:
- Detector: OpenCV's YuNet DNN face detector (5-point landmarks)
- Embedder: the same FaceNet .tflite model Cleer uses, run via tflite-runtime
  (Android/production) or ai-edge-litert (desktop dev -- tflite-runtime has
  no wheel for recent desktop Python/OS combos, same API either way)
- Alignment: eye-level rotation before embedding -- ported with a real fix,
  not a straight port: the original had a ~180 degree rotation bug from
  trusting YuNet's anatomical eye labels instead of actual image position.
  See face_experiment_DELETE_ME/CLEER_ALIGNMENT_BUG_REPORT.md for the detail.
- Quality gates ported from Cleer's FacePipeline.kt: blur rejection, tiny-face
  rejection, duplicate-face dedup, large-group-photo skip. NOT ported (no
  direct equivalent available from this detector): per-landmark presence
  check, and real pitch/yaw head-pose rejection (is_extreme_angle() here is
  an unvalidated approximation, not a measured threshold).

Threshold status: SAME_PERSON_SIMILARITY below is provisional, calibrated
from a small manual test set (see the experiment folder's calibrate.py
output), not a large validated sample. Treat any score near the threshold
as genuinely uncertain.

This module is imported lazily (inside the endpoint handler, not at
app.main's top level) so a machine without opencv/tflite installed doesn't
break the rest of the app -- this feature degrades to "unavailable",
everything else keeps working.
"""
import numpy as np
import cv2

try:
    from tflite_runtime.interpreter import Interpreter  # Android / production
except ImportError:
    from ai_edge_litert.interpreter import Interpreter  # desktop dev fallback

from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
MODEL_PATH = ASSETS_DIR / "facenet_int_quantized.tflite"
YUNET_MODEL_PATH = ASSETS_DIR / "face_detection_yunet_2023mar.onnx"

INPUT_SIZE = 160
CROP_PADDING_FRACTION = 0.3

# Provisional -- see module docstring. Re-validate as real usage data comes in.
SAME_PERSON_SIMILARITY = 0.65

MAX_DIMENSION = 1024
MIN_FACE_SIZE_RATIO = 0.22
MAX_FACES_PER_PHOTO = 15
DUPLICATE_OVERLAP_THRESHOLD = 0.4
MIN_BLUR_VARIANCE = 15.0
BLUR_SAMPLE_SIZE = 64

_face_detector = None
_interpreter = None
_input_details = None
_output_details = None


def _ensure_loaded():
    """Lazy singleton init -- avoids paying model-load cost at import time
    for every process that imports this module transitively."""
    global _face_detector, _interpreter, _input_details, _output_details
    if _interpreter is not None:
        return
    _face_detector = cv2.FaceDetectorYN_create(str(YUNET_MODEL_PATH), "", (320, 320))
    _interpreter = Interpreter(model_path=str(MODEL_PATH))
    _interpreter.allocate_tensors()
    _input_details = _interpreter.get_input_details()
    _output_details = _interpreter.get_output_details()


class NoFaceError(ValueError):
    """Raised whenever a photo is rejected -- no face, too small, too
    blurry, too many faces. Message is safe to show to the user directly."""
    pass


def downscale_if_needed(bgr_image, max_dimension=MAX_DIMENSION):
    h, w = bgr_image.shape[:2]
    scale = max_dimension / max(h, w)
    if scale >= 1.0:
        return bgr_image
    return cv2.resize(bgr_image, (int(w * scale), int(h * scale)))


def iou(box_a, box_b):
    ax, ay, aw, ah = box_a[:4]
    bx, by, bw, bh = box_b[:4]
    left, top = max(ax, bx), max(ay, by)
    right, bottom = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if right <= left or bottom <= top:
        return 0.0
    intersection = (right - left) * (bottom - top)
    union = aw * ah + bw * bh - intersection
    return intersection / union if union > 0 else 0.0


def dedupe_faces(faces):
    by_area_desc = sorted(faces, key=lambda f: -(f[2] * f[3]))
    kept = []
    for face in by_area_desc:
        if not any(iou(k, face) > DUPLICATE_OVERLAP_THRESHOLD for k in kept):
            kept.append(face)
    return kept


def blur_variance(bgr_crop):
    size = BLUR_SAMPLE_SIZE
    small = cv2.resize(bgr_crop, (size, size))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float64)
    lap = cv2.filter2D(gray, -1, np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float64))
    return float(lap.var())


def is_extreme_angle(face_row):
    """NOT a validated measurement -- see module docstring."""
    right_eye, left_eye = face_row[4:6], face_row[6:8]
    nose = face_row[8:10]
    eye_span = np.linalg.norm(left_eye - right_eye)
    if eye_span < 1e-6:
        return False
    eye_mid_x = (left_eye[0] + right_eye[0]) / 2.0
    offset_ratio = abs(nose[0] - eye_mid_x) / eye_span
    return offset_ratio > 0.35


def detect_all_faces(bgr_image):
    _ensure_loaded()
    h, w = bgr_image.shape[:2]
    _face_detector.setInputSize((w, h))
    _, faces = _face_detector.detect(bgr_image)
    if faces is None or len(faces) == 0:
        return []
    return dedupe_faces(list(faces))


def aligned_face_crop(bgr_image, face_row):
    x, y, w, h = face_row[:4]
    # YuNet labels these anatomically (the subject's OWN right/left), which
    # means "right eye" has the SMALLER image x-coordinate. Sorting by actual
    # image position instead of trusting the label is what keeps this a
    # small leveling correction instead of ~180 degrees -- see
    # CLEER_ALIGNMENT_BUG_REPORT.md for how this was found.
    eye_a, eye_b = face_row[4:6], face_row[6:8]
    img_left_eye, img_right_eye = (eye_a, eye_b) if eye_a[0] < eye_b[0] else (eye_b, eye_a)

    eye_mid = (img_left_eye + img_right_eye) / 2.0
    angle_deg = np.degrees(np.arctan2(
        img_right_eye[1] - img_left_eye[1],
        img_right_eye[0] - img_left_eye[0],
    ))

    rot_mat = cv2.getRotationMatrix2D(tuple(eye_mid), angle_deg, 1.0)
    H, W = bgr_image.shape[:2]
    rotated = cv2.warpAffine(bgr_image, rot_mat, (W, H))

    half_w = w * (1 + CROP_PADDING_FRACTION) / 2
    half_h = h * (1 + CROP_PADDING_FRACTION) / 2
    left = int(max(0, eye_mid[0] - half_w))
    top = int(max(0, eye_mid[1] - half_h * 1.2))
    right = int(min(W, eye_mid[0] + half_w))
    bottom = int(min(H, eye_mid[1] + half_h * 1.6))
    crop = rotated[top:bottom, left:right]
    if crop.size > 0:
        return crop

    # Fallback: plain padded crop, no rotation (e.g. degenerate eye_mid).
    xi, yi, wi, hi = [int(round(v)) for v in face_row[:4]]
    pad_x, pad_y = int(wi * CROP_PADDING_FRACTION), int(hi * CROP_PADDING_FRACTION)
    l, t = max(0, xi - pad_x), max(0, yi - pad_y)
    r, b = min(W, xi + wi + pad_x), min(H, yi + hi + pad_y)
    return bgr_image[t:b, l:r]


def prewhiten(rgb_float):
    mean = rgb_float.mean()
    std = rgb_float.std()
    std_adj = max(std, 1.0 / np.sqrt(rgb_float.size))
    return (rgb_float - mean) / std_adj


def embed(face_crop_bgr):
    _ensure_loaded()
    resized = cv2.resize(face_crop_bgr, (INPUT_SIZE, INPUT_SIZE))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32)
    whitened = prewhiten(rgb)
    input_tensor = np.expand_dims(whitened, axis=0)

    _interpreter.set_tensor(_input_details[0]['index'], input_tensor)
    _interpreter.invoke()
    output = _interpreter.get_tensor(_output_details[0]['index'])
    return output[0]


def embed_flipped(face_crop_bgr):
    return embed(cv2.flip(face_crop_bgr, 1))


def cosine_similarity(a, b):
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    return float(dot / (norm_a * norm_b + 1e-6))


def best_similarity(emb_a, flip_a, emb_b, flip_b):
    return max(
        cosine_similarity(emb_a, emb_b),
        cosine_similarity(emb_a, flip_b),
    )


def embed_bgr_image(bgr_image):
    """Core entry point: takes an already-decoded OpenCV BGR image (e.g. from
    cv2.imdecode on uploaded bytes), returns (embedding, flipped_embedding).
    Raises NoFaceError with a user-safe message if the photo is rejected."""
    img = downscale_if_needed(bgr_image)

    faces = detect_all_faces(img)
    if not faces:
        raise NoFaceError("No face detected in this photo.")
    if len(faces) > MAX_FACES_PER_PHOTO:
        raise NoFaceError(f"Too many faces detected ({len(faces)}) -- pick a photo with one person.")

    w = img.shape[1]
    faces = [f for f in faces if f[2] >= w * MIN_FACE_SIZE_RATIO]
    if not faces:
        raise NoFaceError("The face in this photo is too small or unclear.")

    face_row = max(faces, key=lambda f: f[2] * f[3])
    crop = aligned_face_crop(img, face_row)

    variance = blur_variance(crop)
    if variance < MIN_BLUR_VARIANCE:
        raise NoFaceError("This photo is too blurry to use.")

    return embed(crop), embed_flipped(crop)


def embed_photo_bytes(raw_bytes):
    """Convenience wrapper: raw image file bytes -> (embedding, flipped_embedding)."""
    arr = np.frombuffer(raw_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise NoFaceError("Could not read this file as an image.")
    return embed_bgr_image(img)


def embed_bgr_image_with_details(bgr_image):
    """Like embed_bgr_image, but also returns the diagnostic info and the
    actual aligned crop that got embedded -- for the seed-photo upload
    endpoint, where showing the user what was really analyzed (not just a
    checkmark) matters. Not used on the candidate-avatar scoring path (that
    one runs per-candidate at scan volume; this extra work isn't worth
    paying there)."""
    img = downscale_if_needed(bgr_image)

    faces = detect_all_faces(img)
    if not faces:
        raise NoFaceError("No face detected in this photo.")
    if len(faces) > MAX_FACES_PER_PHOTO:
        raise NoFaceError(f"Too many faces detected ({len(faces)}) -- pick a photo with one person.")

    w = img.shape[1]
    sized = [f for f in faces if f[2] >= w * MIN_FACE_SIZE_RATIO]
    if not sized:
        raise NoFaceError("The face in this photo is too small or unclear.")

    face_row = max(sized, key=lambda f: f[2] * f[3])
    crop = aligned_face_crop(img, face_row)

    variance = blur_variance(crop)
    if variance < MIN_BLUR_VARIANCE:
        raise NoFaceError("This photo is too blurry to use.")

    ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return {
        "embedding": embed(crop),
        "flipped": embed_flipped(crop),
        "detection_confidence": float(face_row[14]),
        "blur_variance": variance,
        "faces_in_photo": len(faces),
        "crop_jpeg": buf.tobytes() if ok else None,
    }


def embed_photo_bytes_with_details(raw_bytes):
    arr = np.frombuffer(raw_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise NoFaceError("Could not read this file as an image.")
    return embed_bgr_image_with_details(img)
