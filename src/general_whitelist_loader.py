import os
import cv2
import numpy as np
import psycopg2
import json
import shutil
import concurrent.futures
from tqdm import tqdm
from lib.load_config import load_config_from_file
from lib.init_insightface import initilate_insightface
from lib.database_tools import DirectConnectToDatabase, DirectReleaseConnection
from insightface.app import FaceAnalysis
from lib.output.consolePrint import p_error
import hashlib

def process_single_person(person, face_analyzer: FaceAnalysis, config, failed_dir):
    try:
        # Veritabanına bağlan
        connection = DirectConnectToDatabase(config["database_config"])
        cursor = connection.cursor()

        # Resmi oku ve işle
        image_path = person["local_image_path"]
        if not os.path.exists(image_path):
            return False

        # Zaten var mı kontrol et
        cursor.execute("""
            SELECT COUNT(*) FROM "WhiteListFaces" 
            WHERE "FaceName" = %s
        """, (person["name"],))
        if cursor.fetchone()[0] > 0:
            DirectReleaseConnection(connection)
            return False

        # Resmi parçalar halinde oku
        with open(image_path, 'rb') as f:
            image_data = f.read()

        # CV2 formatına dönüştür
        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # Yüz gömme vektörlerini al
        faces = face_analyzer.get(img)
        
        if not faces:
            # Başarısız resimleri başarısız dizinine taşı
            failed_path = os.path.join(failed_dir, os.path.basename(image_path))
            shutil.copy2(image_path, failed_path)
            DirectReleaseConnection(connection)
            return False

        # Birden fazla yüz varsa, en yüksek algılama puanına sahip olanı al
        if len(faces) > 1:
            face = max(faces, key=lambda x: x.det_score)
        else:
            face = faces[0]

        if face.det_score <= 0.6:
            # Başarısız resimleri başarısız dizinine taşı
            failed_path = os.path.join(failed_dir, os.path.basename(image_path))
            shutil.copy2(image_path, failed_path)
            DirectReleaseConnection(connection)
            return False

        image_hash = hashlib.sha1(image_data).hexdigest()

        cursor.execute("""
            SELECT * FROM "WhiteListFaces" 
            WHERE "FaceImageHash" = %s
        """, (image_hash,))
        if len(cursor.fetchall()) > 0:
            print(f"Resim zaten mevcut: {image_path}")
            DirectReleaseConnection(connection)
            return False

        # Veritabanına ekle
        cursor.execute("""
            INSERT INTO "WhiteListFaces" 
            ("FaceName", "FaceDescription", "FaceImage", "FaceImageHash",
            "FaceEmbeddingData", "Landmarks2d", "FaceBox", "DetectionScore", "FaceGender", "FaceAge")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            person["name"],
            person["description"],
            psycopg2.Binary(image_data),
            image_hash,
            psycopg2.Binary(face.embedding),
            psycopg2.Binary(face.landmark_2d_106),
            psycopg2.Binary(face.bbox),
            float(face.det_score),
            bool(face.gender == 1),
            int(face.age)
        ))
        connection.commit()
        DirectReleaseConnection(connection)
        return True

    except Exception as e:
        p_error(e)
        if 'connection' in locals():
            connection.rollback()
            DirectReleaseConnection(connection)
        return False

def load_whitelist_data(json_path, config, face_analyzer):
    # Başarısız dizini yoksa oluştur
    failed_dir = "failed_faces"
    os.makedirs(failed_dir, exist_ok=True)

    # JSON dosyasından verileri yükle
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    total_count = len(data)
    processed_count = 0
    success_count = 0

    # İş parçacığı havuzu kullanarak işle
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        
        for person in data:
            future = executor.submit(
                process_single_person,
                person,
                face_analyzer,
                config,
                failed_dir
            )
            futures.append(future)

        # İlerlemeyi izle
        for future in tqdm(concurrent.futures.as_completed(futures), total=total_count):
            processed_count += 1
            if future.result():
                success_count += 1

    print(f"\nİşlem tamamlandı:")
    print(f"Toplam işlenen yüz: {processed_count}")
    print(f"Başarılı işlenen yüz: {success_count}")
    print(f"Başarısız işlenen yüz: {processed_count - success_count}")

# Başlat
config_insightface = load_config_from_file()
config = load_config_from_file()[1]
FaceAnalyzer = initilate_insightface(config_insightface)

# JSON dosyasından verileri yükle
import sys
load_whitelist_data(sys.argv[1], config, FaceAnalyzer)