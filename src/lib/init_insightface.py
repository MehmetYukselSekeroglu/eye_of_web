from .output.consolePrint import p_info
from numba import jit
import insightface
import os
import glob
from pathlib import Path

__MODULE_LOG_NAME__ = "INIT_INSIGHTFACE"


def initilate_insightface(main_conf=None, providers=None):
    """
    InsightFace modelini başlatır.

    Args:
        main_conf: Config dictionary veya None (environment variables kullanılır)
        providers: ONNX Runtime providers listesi (örn. ['CUDAExecutionProvider', 'CPUExecutionProvider'])
    """
    p_info("Initilating insightface", locations=__MODULE_LOG_NAME__)

    # DEBUG: Check model path
    home = str(Path.home())
    insightface_dir = os.path.join(home, ".insightface")
    print(f"DEBUG: Checking insightface dir: {insightface_dir}")
    if os.path.exists(insightface_dir):
        print(f"DEBUG: Found {insightface_dir}")
        for root, dirs, files in os.walk(insightface_dir):
            level = root.replace(insightface_dir, "").count(os.sep)
            indent = " " * 4 * (level)
            print(f"{indent}{os.path.basename(root)}/")
            subindent = " " * 4 * (level + 1)
            for f in files:
                print(f"{subindent}{f}")
    else:
        print(f"DEBUG: {insightface_dir} does NOT exist!")

    # Default values for docker image
    default_providers = ["CPUExecutionProvider"]
    # not: antelopev2 kurulumdan sonra 2.bir klasör çıkartması gerektirir
    # bu nedenle docker ortamında tak çalıştır mod için buffalo_l kullanılır
    # insightface bu sorunu çözünce burdada bu çözüm uygulanacak
    # olması gereken yapı: ~/.insightface/models/antelopev2
    # antelopev2 deki durum: ~/.insightface/models/antelopev2/antelopev2
    default_model_name = "buffalo_l"
    # Detection threshold: 0.75 = sadece yüksek güvenilirlikli yüzleri algıla
    # Düşük threshold bozuk embedding'lere ve false positive'lere sebep olur
    default_det_thresh = 0.75
    default_det_size = (640, 640)
    default_ctx_id = 0

    # Config'den değerleri al veya default kullan
    if main_conf is not None and isinstance(main_conf, dict):
        insightface_config = main_conf.get("insightface", {})
        main_config = insightface_config.get("main", {})
        prepare_config = insightface_config.get("prepare", {})

        if providers is None:
            providers = main_config.get("providers", default_providers)
        model_name = main_config.get("name", default_model_name)
        det_thresh = prepare_config.get("det_thresh", default_det_thresh)
        det_size_val = prepare_config.get("det_size", default_det_size)
        ctx_id = prepare_config.get("ctx_id", default_ctx_id)

        # det_size tuple olmalı
        if isinstance(det_size_val, list):
            det_size = tuple(det_size_val)
        else:
            det_size = det_size_val
    else:
        # Config yoksa environment variables veya default değerler kullan
        if providers is None:
            providers = default_providers
        model_name = os.environ.get("INSIGHTFACE_MODEL", default_model_name)
        det_thresh = float(os.environ.get("INSIGHTFACE_DET_THRESH", default_det_thresh))
        det_size = (
            int(os.environ.get("INSIGHTFACE_DET_SIZE_W", 640)),
            int(os.environ.get("INSIGHTFACE_DET_SIZE_H", 640)),
        )
        ctx_id = int(os.environ.get("INSIGHTFACE_CTX_ID", default_ctx_id))

    p_info(
        f"Model: {model_name}, Providers: {providers}, det_thresh: {det_thresh}, det_size: {det_size}",
        locations=__MODULE_LOG_NAME__,
    )

    try:
        app = insightface.app.FaceAnalysis(
            name=model_name,
            providers=providers,
        )

        app.prepare(ctx_id=ctx_id, det_thresh=det_thresh, det_size=det_size)

        p_info("insightface successfuly started.", locations=__MODULE_LOG_NAME__)
        return app
    except FileNotFoundError as fnf_error:
        print(f"Hata: InsightFace model dosyaları bulunamadı: {fnf_error}")
        print(
            "Lütfen modellerin doğru dizinde olduğundan ve config dosyasındaki yolun doğru olduğundan emin olun."
        )
        return None
    except Exception as e:
        print(f"Hata: InsightFace başlatılırken beklenmedik bir sorun oluştu: {str(e)}")
        import traceback

        print(traceback.format_exc())
        return None
