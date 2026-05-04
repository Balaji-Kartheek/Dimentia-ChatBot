"""
Local face authentication helper.
Stores simple image embeddings in DB for local matching.
"""
from typing import Optional, Tuple
import base64
import io
import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover - optional dependency at runtime
    cv2 = None

try:
    import face_recognition
except Exception:  # pragma: no cover - optional dependency at runtime
    face_recognition = None

from config import (
    FACE_AUTH_ENGINE,
    FACE_AUTH_MATCH_THRESHOLD,
    FACE_AUTH_DISTANCE_THRESHOLD,
)


class FaceAuthService:
    def __init__(self, db):
        self.db = db
        self.engine = FACE_AUTH_ENGINE
        self.match_threshold = FACE_AUTH_MATCH_THRESHOLD
        self.distance_threshold = FACE_AUTH_DISTANCE_THRESHOLD

    @property
    def available(self) -> bool:
        if self.engine == "face_recognition":
            return face_recognition is not None
        if self.engine == "cv2":
            return cv2 is not None
        return (face_recognition is not None) or (cv2 is not None)

    def _decode_image(self, image_bytes: bytes):
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    def _embedding_cv2(self, image_bytes: bytes) -> Optional[np.ndarray]:
        if cv2 is None:
            return None
        img = self._decode_image(image_bytes)
        if img is None:
            return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (64, 64))
        vec = resized.astype(np.float32).flatten()
        norm = np.linalg.norm(vec)
        if norm == 0:
            return None
        return vec / norm

    def _embedding_face_recognition(self, image_bytes: bytes) -> Optional[np.ndarray]:
        if face_recognition is None:
            return None
        try:
            img_rgb = face_recognition.load_image_file(io.BytesIO(image_bytes))
        except Exception:
            return None
        encodings = face_recognition.face_encodings(img_rgb)
        if not encodings:
            return None
        return np.array(encodings[0], dtype=np.float32)

    def _embedding(self, image_bytes: bytes) -> Tuple[Optional[np.ndarray], Optional[str]]:
        # Prefer face_recognition when available because it is far more robust across different photos.
        if self.engine in ("auto", "face_recognition"):
            emb = self._embedding_face_recognition(image_bytes)
            if emb is not None:
                return emb, "face_recognition"
            if self.engine == "face_recognition":
                return None, None
        if self.engine in ("auto", "cv2"):
            emb = self._embedding_cv2(image_bytes)
            if emb is not None:
                return emb, "cv2"
        return None, None

    def enroll(self, user_id: str, image_bytes: bytes) -> bool:
        emb, _engine = self._embedding(image_bytes)
        if emb is None:
            return False
        payload = base64.b64encode(emb.tobytes()).decode("utf-8")
        self.db.store_face_embedding(user_id, payload, emb.shape[0])
        return True

    def verify(self, user_id: str, image_bytes: bytes) -> Tuple[bool, float]:
        emb, used_engine = self._embedding(image_bytes)
        if emb is None:
            return False, 0.0
        record = self.db.get_face_embedding(user_id)
        if not record:
            return False, 0.0
        raw = base64.b64decode(record["embedding_base64"].encode("utf-8"))
        saved = np.frombuffer(raw, dtype=np.float32)
        if saved.shape[0] != record["embedding_dim"]:
            return False, 0.0
        if used_engine == "face_recognition" and saved.shape[0] == 128:
            distance = float(np.linalg.norm(saved - emb))
            # UI expects "higher is better score"; map distance to score in [0,1].
            score = max(0.0, 1.0 - min(distance, 1.0))
            return distance <= self.distance_threshold, score
        score = float(np.dot(saved, emb))
        return score >= self.match_threshold, score

