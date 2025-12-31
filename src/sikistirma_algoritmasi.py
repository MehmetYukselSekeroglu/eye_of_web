import cv2
import matplotlib.pyplot as plt
import os
import tempfile
import sys
from PIL import Image
import numpy as np

def format_size(bytes):
    return f"{bytes / 1024:.1f} KB"

# Configuration
image_path = sys.argv[1]  # Replace with your image path
scale_ratio = 0.5

# Read original image
original_img = cv2.imread(image_path)
original_img = cv2.cvtColor(original_img, cv2.COLOR_BGR2RGB)  # Convert to RGB for display

# Get original file size
original_size = os.stat(image_path).st_size

# Resize image
height, width = original_img.shape[:2]
resized_img = cv2.resize(original_img, 
                        (int(width * scale_ratio), 
                        int(height * scale_ratio)), 
                        interpolation=cv2.INTER_CUBIC)

# Calculate resized file size in WebP format
with tempfile.NamedTemporaryFile(suffix='.webp', delete=True) as temp_file:
    pil_img = Image.fromarray(resized_img)
    pil_img.save(temp_file.name, format="WEBP", quality=90)
    resized_webp_size = os.stat(temp_file.name).st_size

# Create figure
plt.figure(figsize=(12, 6))

# Original image
plt.subplot(1, 2, 1)
plt.imshow(original_img)
plt.title(f"Original Image\nDimensions: {height}x{width}\n"
          f"File Size: {format_size(original_size)}")
plt.axis('off')

# Resized image
plt.subplot(1, 2, 2)
plt.imshow(resized_img)
plt.title(f"Resized WebP Image (Ratio: {scale_ratio})\n"
          f"Dimensions: {resized_img.shape[0]}x{resized_img.shape[1]}\n"
          f"WebP Size: {format_size(resized_webp_size)}")
plt.axis('off')

plt.suptitle("Image Size Comparison (Original vs Resized WebP)")
plt.tight_layout()
plt.show()