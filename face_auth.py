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


class FaceAuthService:
    def __init__(self, db):
        self.db = db
        self.match_threshold = 0.90

    @property
    def available(self) -> bool:
        return cv2 is not None

    def _decode_image(self, image_bytes: bytes):
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    def _embedding(self, image_bytes: bytes) -> Optional[np.ndarray]:
        if not self.available:
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

    def enroll(self, user_id: str, image_bytes: bytes) -> bool:
        emb = self._embedding(image_bytes)
        if emb is None:
            return False
        payload = base64.b64encode(emb.tobytes()).decode("utf-8")
        self.db.store_face_embedding(user_id, payload, emb.shape[0])
        return True

    def verify(self, user_id: str, image_bytes: bytes) -> Tuple[bool, float]:
        emb = self._embedding(image_bytes)
        if emb is None:
            return False, 0.0
        record = self.db.get_face_embedding(user_id)
        if not record:
            return False, 0.0
        raw = base64.b64decode(record["embedding_base64"].encode("utf-8"))
        saved = np.frombuffer(raw, dtype=np.float32)
        if saved.shape[0] != record["embedding_dim"]:
            return False, 0.0
        score = float(np.dot(saved, emb))
        return score >= self.match_threshold, score

