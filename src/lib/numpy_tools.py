

import numpy
import cv2
from numba import njit



def buffer2numpy_uint8(buffer_data:bytes) -> numpy.ndarray:
    _data = numpy.frombuffer(buffer_data,dtype=numpy.uint8)
    return _data

def buffer2numpy_float32(buffer_data:bytes) -> numpy.ndarray:
    """
    Args:
        buffer_data (bytes): blob numpy array from postgresql database 

    Returns:
        numpy.ndarray: usable numpy array for python3 
    """
    
    _data = numpy.frombuffer(buffer_data,dtype=numpy.float32)
    return _data


def load_ImageFromContext(image_data) -> numpy.ndarray:
    try:
        image_data = cv2.imdecode(numpy.frombuffer(image_data, numpy.uint8), cv2.IMREAD_COLOR)
        return image_data
    except Exception as err:
        print(f"[!] Image Conver Error: {err}")
        return None


@njit
def compute_cosine_sim(source:numpy.ndarray, target:numpy.ndarray) -> float:
        dot_product_size = numpy.dot(source, target)
        norm_sound1 = numpy.linalg.norm(source)
        norm_sound2 = numpy.linalg.norm(target)

        # kosinus benzerliğini hesaplama 
        GetSimilarity = dot_product_size / (norm_sound1 * norm_sound2)
        return GetSimilarity
    