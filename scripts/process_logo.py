#!/usr/bin/env python3
"""
Process Way-CMS logo: remove background and create favicon.

This script:
1. Removes white/light background from the logo (makes it transparent)
2. Creates a favicon version (32x32 and 16x16)
3. Saves both to cms/static/images/
"""

import sys
from PIL import Image
import os

def remove_background(img, threshold=240):
    """Remove white/light background and make it transparent."""
    # Convert to RGBA if not already
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Get image data
    data = img.getdata()
    
    # Create new image data with transparent background
    new_data = []
    for item in data:
        # If pixel is white/light (R, G, B all > threshold), make it transparent
        if item[0] > threshold and item[1] > threshold and item[2] > threshold:
            new_data.append((255, 255, 255, 0))  # Transparent
        else:
            new_data.append(item)
    
    # Update image data
    img.putdata(new_data)
    return img

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    
    input_path = os.path.join(repo_root, 'cms', 'static', 'images', 'Way-CMS.png')
    output_path = os.path.join(repo_root, 'cms', 'static', 'images', 'way-cms-logo.png')
    favicon_32_path = os.path.join(repo_root, 'cms', 'static', 'images', 'favicon-32x32.png')
    favicon_16_path = os.path.join(repo_root, 'cms', 'static', 'images', 'favicon-16x16.png')
    favicon_ico_path = os.path.join(repo_root, 'cms', 'static', 'favicon.ico')
    
    if not os.path.exists(input_path):
        print(f"Error: Input image not found at {input_path}")
        sys.exit(1)
    
    print(f"Loading image from {input_path}...")
    img = Image.open(input_path)
    print(f"Original size: {img.size}, mode: {img.mode}")
    
    # Remove background
    print("Removing background...")
    img_transparent = remove_background(img, threshold=240)
    
    # Save transparent logo
    print(f"Saving transparent logo to {output_path}...")
    img_transparent.save(output_path, 'PNG')
    
    # Create favicon versions
    print("Creating favicon versions...")
    
    # 32x32 favicon
    favicon_32 = img_transparent.resize((32, 32), Image.Resampling.LANCZOS)
    favicon_32.save(favicon_32_path, 'PNG')
    print(f"Saved {favicon_32_path}")
    
    # 16x16 favicon
    favicon_16 = img_transparent.resize((16, 16), Image.Resampling.LANCZOS)
    favicon_16.save(favicon_16_path, 'PNG')
    print(f"Saved {favicon_16_path}")
    
    # ICO format favicon (for better browser compatibility)
    favicon_ico = img_transparent.resize((32, 32), Image.Resampling.LANCZOS)
    favicon_ico.save(favicon_ico_path, 'ICO', sizes=[(16, 16), (32, 32)])
    print(f"Saved {favicon_ico_path}")
    
    print("\n✅ Logo processing complete!")
    print(f"  - Transparent logo: {output_path}")
    print(f"  - Favicon 32x32: {favicon_32_path}")
    print(f"  - Favicon 16x16: {favicon_16_path}")
    print(f"  - Favicon ICO: {favicon_ico_path}")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
