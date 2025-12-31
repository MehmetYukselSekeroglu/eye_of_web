from pymilvus import connections, utility
from pymilvus.orm.schema import CollectionSchema, FieldSchema, DataType
from pymilvus.orm.collection import Collection

# --- Milvus Connection Configuration ---
MILVUS_HOST = "localhost"  # Replace with your Milvus host
MILVUS_PORT = "19530"    # Replace with your Milvus port
MILVUS_ALIAS = "default"

COLLECTION_PARAMS = {
    "consistency_level": "Strong",  # Options: "Strong", "Bounded", "Session", "Eventually"
}

# --- Helper Function to Connect and Manage Collections ---
def get_or_create_collection(collection_name, fields, primary_field_name, description=""):
    """
    Connects to Milvus, checks if a collection exists, and creates it if it doesn't.
    Returns the Collection object.
    """
    try:
        if not connections.has_connection(MILVUS_ALIAS):
            print(f"Connecting to Milvus at {MILVUS_HOST}:{MILVUS_PORT} under alias '{MILVUS_ALIAS}'...")
            connections.connect(alias=MILVUS_ALIAS, host=MILVUS_HOST, port=MILVUS_PORT)
            print("Connected to Milvus successfully.")
    except Exception as e:
        print(f"Failed to connect to Milvus: {e}")
        raise

    if utility.has_collection(collection_name, using=MILVUS_ALIAS):
        print(f"Collection '{collection_name}' already exists.")
        return Collection(collection_name, using=MILVUS_ALIAS)
    else:
        print(f"Creating collection '{collection_name}'...")
        schema = CollectionSchema(
            fields=fields,
            description=description,
            primary_field=primary_field_name,
            auto_id=True  # ÖNEMLİ: Milvus'un ID üretmesi için True olmalı
        )
        collection = Collection(collection_name, schema=schema, using=MILVUS_ALIAS, **COLLECTION_PARAMS)
        print(f"Collection '{collection_name}' created successfully.")
        return collection

# --- Index Parameters ---
VECTOR_INDEX_PARAMS = {
    "metric_type": "COSINE",  # Or "L2", "IP"
    "index_type": "HNSW",     # Common choices: "HNSW", "IVF_FLAT", "FLAT"
    "params": {"M": 16, "efConstruction": 200},  # Example params for HNSW
}

L2_VECTOR_INDEX_PARAMS = {
    "metric_type": "L2",
    "index_type": "HNSW", # For simplicity, using HNSW. FLAT could be an alternative for low-dim.
    "params": {"M": 16, "efConstruction": 200},
}

# --- Collection Definitions ---

# 1. Milvus Collection for CustomFaceStorage
CUSTOM_FACE_MILVUS_COLLECTION_NAME = "CustomFaceStorageMilvus"
custom_face_milvus_fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
    FieldSchema(name="face_embedding_data", dtype=DataType.FLOAT_VECTOR, dim=512),
    FieldSchema(name="landmarks_2d", dtype=DataType.FLOAT_VECTOR, dim=212),
    FieldSchema(name="face_box", dtype=DataType.FLOAT_VECTOR, dim=4),
    FieldSchema(name="detection_score", dtype=DataType.FLOAT),
    FieldSchema(name="face_gender", dtype=DataType.BOOL),
    FieldSchema(name="face_age", dtype=DataType.INT16),
    FieldSchema(name="detection_date_ts", dtype=DataType.INT64, description="Detection timestamp (Unix epoch)"),
    FieldSchema(name="face_name", dtype=DataType.VARCHAR, max_length=255),
    FieldSchema(name="face_image_hash", dtype=DataType.VARCHAR, max_length=40),
]

# 2. Milvus Collection for WhiteListFaces
WHITE_LIST_FACES_MILVUS_COLLECTION_NAME = "WhiteListFacesMilvus"
# Assuming structure is similar to CustomFaceStorage for vector and face attributes
white_list_faces_milvus_fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
    FieldSchema(name="face_embedding_data", dtype=DataType.FLOAT_VECTOR, dim=512),
    FieldSchema(name="landmarks_2d", dtype=DataType.FLOAT_VECTOR, dim=212),
    FieldSchema(name="face_box", dtype=DataType.FLOAT_VECTOR, dim=4),
    FieldSchema(name="detection_score", dtype=DataType.FLOAT),
    FieldSchema(name="face_gender", dtype=DataType.BOOL),
    FieldSchema(name="face_age", dtype=DataType.INT16),
    FieldSchema(name="detection_date_ts", dtype=DataType.INT64, description="Detection timestamp (Unix epoch)"),
    FieldSchema(name="face_name", dtype=DataType.VARCHAR, max_length=255),
    FieldSchema(name="face_image_hash", dtype=DataType.VARCHAR, max_length=40),
]

# 3. Milvus Collection for ExternalFaceStorage
EXTERNAL_FACE_STORAGE_MILVUS_COLLECTION_NAME = "ExternalFaceStorageMilvus"
external_face_milvus_fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
    FieldSchema(name="face_embedding_data", dtype=DataType.FLOAT_VECTOR, dim=512),
    FieldSchema(name="landmarks_2d", dtype=DataType.FLOAT_VECTOR, dim=212),
    FieldSchema(name="face_box", dtype=DataType.FLOAT_VECTOR, dim=4),
    FieldSchema(name="detection_score", dtype=DataType.FLOAT),
    FieldSchema(name="face_gender", dtype=DataType.BOOL),
    FieldSchema(name="face_age", dtype=DataType.INT16),
    FieldSchema(name="alarm", dtype=DataType.BOOL),
    FieldSchema(name="detection_date_ts", dtype=DataType.INT64, description="Detection timestamp (Unix epoch)"),
    FieldSchema(name="face_name", dtype=DataType.VARCHAR, max_length=255),
    FieldSchema(name="image_hash", dtype=DataType.VARCHAR, max_length=40),
]

# 4. Milvus Collection for EgmArananlar
EGM_ARANANLAR_MILVUS_COLLECTION_NAME = "EgmArananlarMilvus"
egm_arananlar_milvus_fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
    FieldSchema(name="face_embedding_data", dtype=DataType.FLOAT_VECTOR, dim=512),
    FieldSchema(name="landmarks_2d", dtype=DataType.FLOAT_VECTOR, dim=212),
    FieldSchema(name="face_box", dtype=DataType.FLOAT_VECTOR, dim=4),
    FieldSchema(name="detection_score", dtype=DataType.FLOAT),
    FieldSchema(name="face_gender", dtype=DataType.BOOL),
    FieldSchema(name="face_age", dtype=DataType.INT16),
    FieldSchema(name="detection_date_ts", dtype=DataType.INT64, description="Detection timestamp (Unix epoch)"),
    FieldSchema(name="face_name", dtype=DataType.VARCHAR, max_length=255),
    FieldSchema(name="organizer", dtype=DataType.VARCHAR, max_length=255),
    FieldSchema(name="organizer_level", dtype=DataType.VARCHAR, max_length=255),
    FieldSchema(name="birth_date_and_location", dtype=DataType.VARCHAR, max_length=255),
    FieldSchema(name="image_hash", dtype=DataType.VARCHAR, max_length=40),
]

# 5. Milvus Collection for EyeOfWebFaceID's vector data
EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME = "EyeOfWebFaceDataMilvus"
eye_of_web_face_data_milvus_fields = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=False),
    FieldSchema(name="face_embedding_data", dtype=DataType.FLOAT_VECTOR, dim=512),
    FieldSchema(name="landmarks_2d", dtype=DataType.FLOAT_VECTOR, dim=212),
    FieldSchema(name="face_box", dtype=DataType.FLOAT_VECTOR, dim=4),
    FieldSchema(name="detection_score", dtype=DataType.FLOAT),
    FieldSchema(name="face_gender", dtype=DataType.BOOL),
    FieldSchema(name="face_age", dtype=DataType.INT16),
    FieldSchema(name="detection_date_ts", dtype=DataType.INT64, description="Detection timestamp (Unix epoch)"),
]


# --- Main Function to Setup Milvus ---
def setup_milvus_collections_and_indexes():
    """
    Creates all defined Milvus collections and necessary indexes.
    """
    collection_configs = [
        {
            "name": CUSTOM_FACE_MILVUS_COLLECTION_NAME,
            "fields": custom_face_milvus_fields,
            "description": "Stores face vector data from CustomFaceStorage SQL table.",
            "vector_indexes": [
                {"field_name": "face_embedding_data", "params": VECTOR_INDEX_PARAMS},
                {"field_name": "landmarks_2d", "params": L2_VECTOR_INDEX_PARAMS},
                {"field_name": "face_box", "params": L2_VECTOR_INDEX_PARAMS}
            ],
            "scalar_indexes": ["face_name", "face_image_hash"]
        },
        {
            "name": WHITE_LIST_FACES_MILVUS_COLLECTION_NAME,
            "fields": white_list_faces_milvus_fields,
            "description": "Stores face vector data from WhiteListFaces SQL table.",
            "vector_indexes": [
                {"field_name": "face_embedding_data", "params": VECTOR_INDEX_PARAMS},
                {"field_name": "landmarks_2d", "params": L2_VECTOR_INDEX_PARAMS},
                {"field_name": "face_box", "params": L2_VECTOR_INDEX_PARAMS}
            ],
            "scalar_indexes": ["face_name", "face_image_hash"]
        },
        {
            "name": EXTERNAL_FACE_STORAGE_MILVUS_COLLECTION_NAME,
            "fields": external_face_milvus_fields,
            "description": "Stores face vector data from ExternalFaceStorage SQL table.",
            "vector_indexes": [
                {"field_name": "face_embedding_data", "params": VECTOR_INDEX_PARAMS},
                {"field_name": "landmarks_2d", "params": L2_VECTOR_INDEX_PARAMS},
                {"field_name": "face_box", "params": L2_VECTOR_INDEX_PARAMS}
            ],
            "scalar_indexes": ["face_name", "image_hash", "alarm"]
        },
        {
            "name": EGM_ARANANLAR_MILVUS_COLLECTION_NAME,
            "fields": egm_arananlar_milvus_fields,
            "description": "Stores face vector data from EgmArananlar SQL table.",
            "vector_indexes": [
                {"field_name": "face_embedding_data", "params": VECTOR_INDEX_PARAMS},
                {"field_name": "landmarks_2d", "params": L2_VECTOR_INDEX_PARAMS},
                {"field_name": "face_box", "params": L2_VECTOR_INDEX_PARAMS}
            ],
            "scalar_indexes": ["face_name", "image_hash", "organizer", "organizer_level"]
        },
        {
            "name": EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME,
            "fields": eye_of_web_face_data_milvus_fields,
            "description": "Stores face features, referenced by EyeOfWebFaceID SQL table.",
            "vector_indexes": [
                {"field_name": "face_embedding_data", "params": VECTOR_INDEX_PARAMS},
                {"field_name": "landmarks_2d", "params": L2_VECTOR_INDEX_PARAMS},
                {"field_name": "face_box", "params": L2_VECTOR_INDEX_PARAMS}
            ],
            "scalar_indexes": []
        },
    ]

    for config in collection_configs:
        # Correctly pass primary_field_name, which is 'milvus_id' for all
        collection = get_or_create_collection(
            config["name"],
            config["fields"],
            primary_field_name="id", # The field designated as primary (auto_id handles its generation)
            description=config["description"]
        )

        # Create vector index
        for vec_idx_config in config.get("vector_indexes", []):
            vector_field_name = vec_idx_config["field_name"]
            index_params = vec_idx_config["params"]
            vector_index_name = f"idx_vector_{vector_field_name}"
            if not collection.has_index(index_name=vector_index_name):
                print(f"Creating vector index '{vector_index_name}' on field '{vector_field_name}' for collection '{config['name']}' with params {index_params}...")
                collection.create_index(vector_field_name, index_params, index_name=vector_index_name)
                print(f"Vector index '{vector_index_name}' created.")
            else:
                print(f"Vector index '{vector_index_name}' already exists on collection '{config['name']}'.")

        # Create scalar indexes
        for scalar_field in config.get("scalar_indexes", []):
            scalar_index_name = f"idx_scalar_{scalar_field}"
            if not collection.has_index(index_name=scalar_index_name):
                try:
                    print(f"Creating scalar index '{scalar_index_name}' on field '{scalar_field}' for collection '{config['name']}'...")
                    # Default index type for scalar fields is usually fine (e.g., STL_SORT or Marisa Trie for strings)
                    collection.create_index(scalar_field, index_name=scalar_index_name)
                    print(f"Scalar index '{scalar_index_name}' created.")
                except Exception as e:
                    print(f"Could not create scalar index '{scalar_index_name}' on field '{scalar_field}': {e}")
            else:
                print(f"Scalar index '{scalar_index_name}' already exists on collection '{config['name']}'.")
        
        # Corrected loading: Specify vector fields that have indexes
        indexed_vector_fields = [
            idx_conf["field_name"] for idx_conf in config.get("vector_indexes", [])
        ]

        if indexed_vector_fields:
            print(f"Loading collection '{config['name']}' for indexed vector fields: {indexed_vector_fields}...")
            collection.load(field_names=indexed_vector_fields)
            print(f"Collection '{config['name']}' loaded for fields: {indexed_vector_fields}.")
        else:
            # If no vector indexes are defined in this specific config for the collection,
            # a generic load might be acceptable, or it might indicate a non-vector collection
            # or a collection where indexes are not managed by this script's vector_indexes section.
            print(f"Loading collection '{config['name']}' with a generic load call (no specific indexed vector fields found in this configuration).")
            collection.load()
            print(f"Collection '{config['name']}' loaded (generic call).")


if __name__ == "__main__":
    print("Starting Milvus schema setup script...")
    try:
        setup_milvus_collections_and_indexes()
        print("Milvus schema setup script finished successfully.")
    except Exception as e:
        print(f"An error occurred during Milvus schema setup: {e}")
    finally:
        # Optional: Disconnect if no further operations are needed immediately
        # if connections.has_connection(MILVUS_ALIAS):
        #     connections.disconnect(MILVUS_ALIAS)
        #     print(f"Disconnected from Milvus alias '{MILVUS_ALIAS}'.")
        pass
