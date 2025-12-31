from pymilvus import connections, utility
from pymilvus.orm.collection import Collection

# Import configuration from the schema generator
from MILVUS_SCHEMA_GENERATOR import (
    MILVUS_HOST, MILVUS_PORT, MILVUS_ALIAS,
    CUSTOM_FACE_MILVUS_COLLECTION_NAME,
    WHITE_LIST_FACES_MILVUS_COLLECTION_NAME,
    EXTERNAL_FACE_STORAGE_MILVUS_COLLECTION_NAME,
    EGM_ARANANLAR_MILVUS_COLLECTION_NAME,
    EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME
)

# Auto index parameters
AUTO_VECTOR_INDEX_PARAMS = {
    "metric_type": "COSINE",  # This can still be specified
    "index_type": "AUTO",     # Using AUTO instead of explicit HNSW/IVF_FLAT/etc.
    "params": {},             # Empty params lets Milvus optimize
}

AUTO_L2_VECTOR_INDEX_PARAMS = {
    "metric_type": "L2",      # This can still be specified
    "index_type": "AUTO",     # Using AUTO 
    "params": {},             # Empty params lets Milvus optimize
}

def connect_to_milvus():
    """Establish connection to Milvus server"""
    try:
        if not connections.has_connection(MILVUS_ALIAS):
            print(f"Connecting to Milvus at {MILVUS_HOST}:{MILVUS_PORT} under alias '{MILVUS_ALIAS}'...")
            connections.connect(alias=MILVUS_ALIAS, host=MILVUS_HOST, port=MILVUS_PORT)
            print("Connected to Milvus successfully.")
        return True
    except Exception as e:
        print(f"Failed to connect to Milvus: {e}")
        return False

def change_indexes_to_auto(collection_name, vector_field_configs):
    """
    Change existing indexes to auto indexes for the given collection.
    
    Args:
        collection_name: Name of the collection to modify
        vector_field_configs: List of dicts with field_name and metric_type
    """
    if not utility.has_collection(collection_name):
        print(f"Collection '{collection_name}' does not exist. Skipping.")
        return False
    
    collection = Collection(collection_name)
    
    try:
        collection.release()
        print(f"Released collection '{collection_name}' from memory.")
    except Exception as e:
        print(f"Note: Could not release collection '{collection_name}': {e}. Continuing...")
    
    for config in vector_field_configs:
        field_name = config["field_name"]
        metric_type = config["metric_type"]
        
        # Drop existing index for this specific field_name
        try:
            existing_indexes = collection.indexes
            for idx in existing_indexes:
                if idx.field_name == field_name:
                    print(f"Attempting to drop existing index '{idx.index_name}' on field '{field_name}'...")
                    collection.drop_index(index_name=idx.index_name) # Use index_name attribute
                    print(f"Dropped index '{idx.index_name}' on field '{field_name}'.")
                    break # Assuming one index per vector field relevant to this script
        except Exception as e:
            print(f"Note: Error or no index to drop for field '{field_name}': {e}")
        
        # Create new auto index
        auto_index_params = {
            "metric_type": metric_type,
            "index_type": "AUTOINDEX",  # Changed from "AUTO" to "AUTOINDEX"
            "params": {} # Empty params for AUTOINDEX
        }
        
        auto_index_name = f"auto_idx_{field_name}" # Define a new name for the auto index
        print(f"Creating auto index '{auto_index_name}' on field '{field_name}' with params {auto_index_params}...")
        try:
            collection.create_index(field_name, auto_index_params, index_name=auto_index_name)
            print(f"Created auto index '{auto_index_name}' on field '{field_name}'.")
        except Exception as e:
            print(f"Error creating auto index '{auto_index_name}' on '{field_name}': {e}")
            print(f"Attempted params: {auto_index_params}")

    print(f"Loading collection '{collection_name}'...")
    try:
        collection.load()
        print(f"Collection '{collection_name}' loaded.")
    except Exception as e:
        print(f"Error loading collection '{collection_name}': {e}")
    
    return True

def update_all_collections():
    """Update all collections to use auto indexes"""
    if not connect_to_milvus():
        return False
    
    # Configuration for all collections and their vector fields
    collections_config = [
        {
            "name": CUSTOM_FACE_MILVUS_COLLECTION_NAME,
            "vector_fields": [
                {"field_name": "face_embedding_data", "metric_type": "COSINE"},
                {"field_name": "landmarks_2d", "metric_type": "L2"},
                {"field_name": "face_box", "metric_type": "L2"}
            ]
        },
        {
            "name": WHITE_LIST_FACES_MILVUS_COLLECTION_NAME,
            "vector_fields": [
                {"field_name": "face_embedding_data", "metric_type": "COSINE"},
                {"field_name": "landmarks_2d", "metric_type": "L2"},
                {"field_name": "face_box", "metric_type": "L2"}
            ]
        },
        {
            "name": EXTERNAL_FACE_STORAGE_MILVUS_COLLECTION_NAME,
            "vector_fields": [
                {"field_name": "face_embedding_data", "metric_type": "COSINE"},
                {"field_name": "landmarks_2d", "metric_type": "L2"},
                {"field_name": "face_box", "metric_type": "L2"}
            ]
        },
        {
            "name": EGM_ARANANLAR_MILVUS_COLLECTION_NAME,
            "vector_fields": [
                {"field_name": "face_embedding_data", "metric_type": "COSINE"},
                {"field_name": "landmarks_2d", "metric_type": "L2"},
                {"field_name": "face_box", "metric_type": "L2"}
            ]
        },
        {
            "name": EYE_OF_WEB_FACE_DATA_MILVUS_COLLECTION_NAME,
            "vector_fields": [
                {"field_name": "face_embedding_data", "metric_type": "COSINE"},
                {"field_name": "landmarks_2d", "metric_type": "L2"},
                {"field_name": "face_box", "metric_type": "L2"}
            ]
        }
    ]
    
    success_count = 0
    total_collections = len(collections_config)
    for config in collections_config:
        print(f"\n{'='*50}")
        print(f"Processing collection: {config['name']}")
        print(f"{'='*50}")
        
        if change_indexes_to_auto(config["name"], config["vector_fields"]):
            success_count += 1
    
    print(f"\nSuccessfully processed {success_count} out of {total_collections} collections.")
    return True

if __name__ == "__main__":
    print("Starting index conversion to AUTOINDEX...\n")
    try:
        update_all_collections()
        print("\nIndex conversion script finished.")
    except Exception as e:
        print(f"\nAn unexpected error occurred during the update process: {e}")
    finally:
        # Optional: Disconnect if no further operations are needed
        if connections.has_connection(MILVUS_ALIAS):
            connections.disconnect(MILVUS_ALIAS)
            print(f"Disconnected from Milvus alias '{MILVUS_ALIAS}'.")
