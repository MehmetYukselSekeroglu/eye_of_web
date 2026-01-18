import cv2
import numpy as np
import PIL
import zlib
import struct
import io
import os  # Added for main block
import sys  # Added for main block
import matplotlib.pyplot as plt  # Added for visualization
from PIL import Image

SCALA_RATIO = 0.5


def compress_image(image_binary):
    """
    Compress an image using a multi-step process:
    1. Convert raw image to resized image
    2. Convert to WebP lossy format (quality=90)
    3. Apply zlib compression

    Args:
        image_binary (bytes): Raw image binary data

    Returns:
        bytes: Compressed binary data
    """
    # Convert binary to numpy array
    image_array = np.frombuffer(image_binary, np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode input image binary.")

    # Get original dimensions
    height, width = image.shape[:2]

    # Resize image
    scale_ratio = SCALA_RATIO  # You can adjust this ratio if needed
    resized_img = cv2.resize(
        image,
        (int(width * scale_ratio), int(height * scale_ratio)),
        interpolation=cv2.INTER_CUBIC,
    )

    # Convert to WebP lossy format using PIL
    pil_img = Image.fromarray(cv2.cvtColor(resized_img, cv2.COLOR_BGR2RGB))
    webp_buffer = io.BytesIO()
    # Use quality=90 (lossy) instead of lossless=True
    pil_img.save(webp_buffer, format="WEBP", quality=90)
    webp_binary = webp_buffer.getvalue()

    # Apply zlib compression
    compressed_binary = zlib.compress(webp_binary, level=9)  # Maximum compression

    return compressed_binary


def decompress_image(compressed_binary):
    """
    Decompress an image that was compressed with compress_image function

    Args:
        compressed_binary (bytes): Compressed binary data

    Returns:
        bytes: Decompressed image binary (as PNG)
    """
    # Decompress zlib
    webp_binary = zlib.decompress(compressed_binary)

    # Load WebP image (handles both lossy and lossless)
    webp_buffer = io.BytesIO(webp_binary)
    try:
        pil_img = Image.open(webp_buffer)
    except PIL.UnidentifiedImageError:
        raise ValueError("Could not decode WebP data after zlib decompression.")

    # Convert to OpenCV format (BGR)
    img_array = np.array(pil_img)
    # Ensure conversion handles different image modes (RGB, RGBA, Grayscale) from WebP
    if pil_img.mode == "RGB":
        img_array_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    elif pil_img.mode == "RGBA":
        img_array_bgr = cv2.cvtColor(
            img_array, cv2.COLOR_RGBA2BGR
        )  # Convert RGBA to BGR
    elif pil_img.mode == "L":  # Grayscale
        img_array_bgr = cv2.cvtColor(
            img_array, cv2.COLOR_GRAY2BGR
        )  # Convert grayscale to BGR
    else:
        # Fallback or raise error for unsupported modes
        print(
            f"Warning: Unexpected PIL image mode '{pil_img.mode}'. Attempting direct use."
        )
        img_array_bgr = img_array

    # Encode to PNG binary for lossless comparison/output
    success, png_binary_encoded = cv2.imencode(".png", img_array_bgr)
    if not success:
        raise ValueError("Could not encode decompressed image to PNG")

    return png_binary_encoded.tobytes()


def format_size(bytes_val):
    """Helper function to format bytes into KB"""
    if bytes_val < 0:
        return "N/A"  # Handle potential errors
    return f"{bytes_val / 1024:.2f} KB"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python compress_tools.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]

    if not os.path.exists(image_path):
        print(f"Error: Image file not found at '{image_path}'")
        sys.exit(1)

    try:
        # Read original image binary
        with open(image_path, "rb") as f:
            original_binary = f.read()
        original_size = len(original_binary)

        # Decode original for display
        original_img_np = np.frombuffer(original_binary, np.uint8)
        original_img_cv = cv2.imdecode(original_img_np, cv2.IMREAD_COLOR)
        if original_img_cv is None:
            raise ValueError("Could not decode original image for display.")
        original_img_rgb = cv2.cvtColor(
            original_img_cv, cv2.COLOR_BGR2RGB
        )  # For matplotlib
        original_height, original_width = original_img_cv.shape[:2]

        print(f"Original Image: {image_path}")
        print(f"Original Size: {format_size(original_size)}")
        print(f"Original Dimensions: {original_height}x{original_width}")

        # --- Perform Resizing ---
        scale_ratio = 0.5  # Match the ratio used in compress_image
        resized_img_cv = cv2.resize(
            original_img_cv,
            (int(original_width * scale_ratio), int(original_height * scale_ratio)),
            interpolation=cv2.INTER_CUBIC,
        )
        resized_img_rgb = cv2.cvtColor(
            resized_img_cv, cv2.COLOR_BGR2RGB
        )  # For matplotlib
        resized_height, resized_width = resized_img_cv.shape[:2]
        print(f"Resized Dimensions: {resized_height}x{resized_width}")

        # Estimate resized size by encoding to WebP (Q=90) in memory
        pil_resized_img = Image.fromarray(resized_img_rgb)  # Use RGB for PIL
        webp_q90_buffer = io.BytesIO()
        pil_resized_img.save(webp_q90_buffer, format="WEBP", quality=90)
        resized_webp_q90_size = len(webp_q90_buffer.getvalue())
        print(
            f"Estimated Resized Size (WebP Q=90): {format_size(resized_webp_q90_size)}"
        )
        # --- End Resizing and Size Estimation ---

        # Compress (using the full function: Resize -> WebP Q90 -> Zlib)
        compressed_data = compress_image(original_binary)
        compressed_size = len(compressed_data)
        print(
            f"Final Compressed Size (Resized -> WebP Q90 -> Zlib): {format_size(compressed_size)}"
        )

        # Decompress (using the full function)
        decompressed_binary = decompress_image(compressed_data)
        decompressed_size = len(decompressed_binary)  # Size of the PNG binary
        print(f"Decompressed Size (as PNG): {format_size(decompressed_size)}")

        # --- Visualization ---
        plt.figure(figsize=(12, 6))

        # Original image
        plt.subplot(1, 2, 1)
        plt.imshow(original_img_rgb)
        plt.title(
            f"Original Image\nDimensions: {original_height}x{original_width}\nFile Size: {format_size(original_size)}"
        )
        plt.axis("off")

        # Resized image
        plt.subplot(1, 2, 2)
        plt.imshow(resized_img_rgb)
        # Update title to show WebP Q90 size
        plt.title(
            f"Resized Image (Ratio: {scale_ratio})\n"
            f"Dimensions: {resized_height}x{resized_width}\n"
            f"Estimated WebP (Q=90) Size: {format_size(resized_webp_q90_size)}"
        )
        plt.axis("off")

        plt.suptitle("Image Size Comparison (Original vs Resized)")
        plt.tight_layout(
            rect=[0, 0.03, 1, 0.95]
        )  # Adjust layout to prevent title overlap
        plt.show()
        # --- End Visualization ---

    except FileNotFoundError:
        print(f"Error: Could not find the image file: {image_path}")
    except ValueError as ve:  # Catch specific ValueErrors
        print(f"Processing Error: {ve}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred during processing: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
