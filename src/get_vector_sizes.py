from lib.load_config import load_config_from_file
from lib.init_insightface import initilate_insightface
import cv2
import numpy as np

config = load_config_from_file()

insightface_model = initilate_insightface(config)

image_cv2 = cv2.imread("/home/wesker/Pictures/cihat_sekeroglu.png")

results = insightface_model.get(image_cv2)

print(f"**************************************")
print(f"""
Embeddings Size: {len(results[0].embedding)}
Landmarks Size: {len(results[0].landmark_2d_106)}
Face Box Size: {len(results[0].bbox)}
      """)
print(f"**************************************")

