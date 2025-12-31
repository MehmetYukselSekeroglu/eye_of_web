from .output.consolePrint import p_info
from numba import jit
import insightface
import os

__MODULE_LOG_NAME__ = "INIT_INSIGHTFACE"

def initilate_insightface(main_conf, providers=None):
    p_info("Initilating insightface", locations=__MODULE_LOG_NAME__)
    
    # Get providers from config or use default
    if providers is None:
        providers = main_conf[1].get('insightface', {}).get('main', {}).get('providers', ['CPUExecutionProvider'])
    
    # Get model name from config
    model_name = main_conf[1].get('insightface', {}).get('main', {}).get('name', 'buffalo_l')
    
    # Get detection parameters
    det_thresh = main_conf[1]["insightface"]["prepare"]["det_thresh"]
    det_size = main_conf[1]["insightface"]["prepare"]["det_size"]
    ctx_id = main_conf[1]["insightface"]["prepare"]["ctx_id"]

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
        print("Lütfen modellerin doğru dizinde olduğundan ve config dosyasındaki yolun doğru olduğundan emin olun.")
        return None
    except Exception as e:
        print(f"Hata: InsightFace başlatılırken beklenmedik bir sorun oluştu: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None
