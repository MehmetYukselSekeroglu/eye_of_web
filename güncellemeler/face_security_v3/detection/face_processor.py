"""
Yüz algılama ve tanıma motoru.
InsightFace buffalo_s modeli kullanır.
GPU mevcutsa otomatik olarak CUDA seçilir.
"""
import logging

import numpy as np

logger = logging.getLogger(__name__)


def _get_providers() -> list[str]:
    """Kullanılabilir ONNX Runtime provider'larını döner (GPU öncelikli)."""
    try:
        import onnxruntime as ort
        available = ort.get_available_providers()
        if "CUDAExecutionProvider" in available:
            logger.info("GPU tespit edildi — CUDA kullanılıyor.")
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    except ImportError:
        pass
    logger.info("GPU bulunamadı — CPU kullanılıyor.")
    return ["CPUExecutionProvider"]


class FaceProcessor:
    def __init__(self, model_name: str = "buffalo_s", det_size: tuple = (640, 640)):
        from insightface.app import FaceAnalysis

        providers = _get_providers()
        self.app = FaceAnalysis(name=model_name, providers=providers)
        self.app.prepare(ctx_id=0, det_size=det_size)
        self.known_faces: dict[str, np.ndarray] = {}

    # ── Veritabanı ───────────────────────────────────────────────────────────

    def load_embeddings(self, embeddings: dict[str, np.ndarray]) -> None:
        """Önbellekten hesaplanmış embedding sözlüğünü yükler."""
        self.known_faces = embeddings
        logger.info("Embedding'ler yüklendi: %d kişi", len(self.known_faces))

    # ── Tespit ───────────────────────────────────────────────────────────────

    def get_faces(self, frame: np.ndarray) -> list:
        """Karede yüzleri algılar ve InsightFace nesneleri listesi döner."""
        try:
            return self.app.get(frame)
        except Exception as e:
            logger.debug("Yüz algılama hatası: %s", e)
            return []

    def recognize(
        self, face, threshold: float = 0.45
    ) -> tuple[str, float]:
        """
        Tek bir InsightFace nesnesi için en yakın kişiyi bulur.
        Döner: (name, score)
        score < threshold ise name = "unknown"
        """
        emb = face.embedding
        norm = np.linalg.norm(emb)
        if norm == 0:
            return "unknown", 0.0
        emb = emb / norm

        best_score, best_name = -1.0, "unknown"
        for k_name, k_emb in self.known_faces.items():
            score = float(np.dot(emb, k_emb))
            if score > best_score:
                best_score, best_name = score, k_name

        if best_score < threshold:
            return "unknown", best_score
        return best_name, best_score
