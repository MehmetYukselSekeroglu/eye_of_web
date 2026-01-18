import os
import sys
import cv2
import numpy as np
import psycopg2
from psycopg2.extras import DictCursor
from lib.compress_tools import decompress_image
from lib.database_tools import DatabaseTools, get_milvus_collection

# Setup
db_tools = DatabaseTools()
conn = db_tools.connect()
cursor = conn.cursor(cursor_factory=DictCursor)


def check_face(face_id):
    print(f"--- Checking FaceID {face_id} ---")

    # 1. Get MilvusRefID
    cursor.execute(
        'SELECT "MilvusRefID", "ImageID" FROM "EyeOfWebFaceID" WHERE "ID" = %s',
        (face_id,),
    )
    res = cursor.fetchone()
    if not res:
        print(f"FaceID {face_id} not found in EyeOfWebFaceID")
        return

    milvus_ref_id = res["MilvusRefID"]
    image_id = res["ImageID"]
    print(f"MilvusRefID: {milvus_ref_id}, ImageID: {image_id}")

    # 2. Get Image
    cursor.execute('SELECT "BinaryImage" FROM "ImageID" WHERE "ID" = %s', (image_id,))
    img_res = cursor.fetchone()
    if not img_res or not img_res["BinaryImage"]:
        print("Image binary not found")
        return

    img_bin = bytes(img_res["BinaryImage"])
    try:
        decompressed = decompress_image(img_bin)
        arr = np.frombuffer(decompressed, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        h, w = img.shape[:2]
        print(f"Image Dims: {w}x{h}")
    except Exception as e:
        print(f"Image decode failed: {e}")
        return

    # 3. Get Milvus Data
    col = get_milvus_collection("EyeOfWebFaceDataMilvus")  # Hardcoded from code
    if not col:
        print("Milvus collection not found")
        return

    m_res = col.query(expr=f"id == {milvus_ref_id}", output_fields=["face_box"])
    if not m_res:
        print("Milvus data not found")
        return

    bbox = m_res[0]["face_box"]
    print(f"FaceBox: {bbox}")

    x1, y1, x2, y2 = bbox
    print(f"BBox width: {x2-x1}, height: {y2-y1}")

    # Check bounds
    if x2 > w or y2 > h:
        print("CRITICAL: BBox is OUT OF BOUNDS of the image! Likely scaling issue.")
        print(f"Exceeds by: x={x2-w if x2>w else 0}, y={y2-h if y2>h else 0}")
    else:
        print("BBox is within image bounds.")

    # Check for 0.5x scaling evidence
    # If bbox seems small relative to typical face size? Hard to say without visual.

    # Save debug image
    cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
    out_name = f"debug_face_{face_id}.jpg"
    cv2.imwrite(out_name, img)
    print(f"Saved debug image to {out_name}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        ids = sys.argv[1:]
        for i in ids:
            check_face(int(i))
    else:
        print("Usage: python3 verify.py <face_id1> [face_id2 ...]")
