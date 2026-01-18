import os
import shutil
from pathlib import Path


def setup_models():
    """
    Copies InsightFace models from local home directory to the build context
    so they can be included in the Docker image without re-downloading.
    """
    # Source path (User's home directory)
    home_dir = Path.home()
    source_model_dir = home_dir / ".insightface" / "models" / "buffalo_l"

    # Destination path (Script directory)
    # We'll create a hidden folder .insightface_cache/models/buffalo_l relative to this script
    script_dir = Path(__file__).parent.absolute()
    dest_base_dir = script_dir / ".insightface_cache" / "models"
    dest_model_dir = dest_base_dir / "buffalo_l"

    print(f"Checking for models at: {source_model_dir}")

    if not source_model_dir.exists():
        print(f"Warning: Local models not found at {source_model_dir}")
        print("Docker build may download models during image creation.")
        return

    # Check if destination already exists and is up to date?
    # For simplicity, we can just clear and copy to be safe, or check if it exists.
    if dest_model_dir.exists():
        print(f"Removing existing cache at {dest_model_dir} to ensure freshness...")
        shutil.rmtree(dest_model_dir)

    print(f"Copying models to {dest_model_dir}...")
    try:
        os.makedirs(dest_base_dir, exist_ok=True)
        shutil.copytree(source_model_dir, dest_model_dir)
        print("Success! Models copied to build context.")
        print(f"You can now run: docker build -t your_image_name .")
    except Exception as e:
        print(f"Error copying models: {e}")


if __name__ == "__main__":
    setup_models()
