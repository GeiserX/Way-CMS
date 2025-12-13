#!/bin/bash
# Simple script to create transparent logo and favicon using sips (macOS)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
INPUT="$REPO_ROOT/cms/static/images/Way-CMS.png"
OUTPUT="$REPO_ROOT/cms/static/images/way-cms-logo.png"
FAVICON_32="$REPO_ROOT/cms/static/images/favicon-32x32.png"
FAVICON_16="$REPO_ROOT/cms/static/images/favicon-16x16.png"
FAVICON_ICO="$REPO_ROOT/cms/static/favicon.ico"

if [ ! -f "$INPUT" ]; then
    echo "Error: Input image not found at $INPUT"
    exit 1
fi

echo "Creating transparent logo and favicons..."

# For now, just copy and resize (transparency will need Python/PIL)
# We'll use Python with a minimal script

python3 << 'PYTHON_SCRIPT'
import sys
import os

try:
    from PIL import Image
except ImportError:
    print("Installing Pillow...")
    os.system(f"{sys.executable} -m pip install Pillow --quiet")
    from PIL import Image

script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.dirname(script_dir)

input_path = os.path.join(repo_root, 'cms', 'static', 'images', 'Way-CMS.png')
output_path = os.path.join(repo_root, 'cms', 'static', 'images', 'way-cms-logo.png')
favicon_32_path = os.path.join(repo_root, 'cms', 'static', 'images', 'favicon-32x32.png')
favicon_16_path = os.path.join(repo_root, 'cms', 'static', 'images', 'favicon-16x16.png')
favicon_ico_path = os.path.join(repo_root, 'cms', 'static', 'favicon.ico')

img = Image.open(input_path)
if img.mode != 'RGBA':
    img = img.convert('RGBA')

data = img.getdata()
new_data = []
threshold = 240
for item in data:
    if item[0] > threshold and item[1] > threshold and item[2] > threshold:
        new_data.append((255, 255, 255, 0))
    else:
        new_data.append(item)

img.putdata(new_data)
img.save(output_path, 'PNG')

favicon_32 = img.resize((32, 32), Image.Resampling.LANCZOS)
favicon_32.save(favicon_32_path, 'PNG')

favicon_16 = img.resize((16, 16), Image.Resampling.LANCZOS)
favicon_16.save(favicon_16_path, 'PNG')

favicon_ico = img.resize((32, 32), Image.Resampling.LANCZOS)
favicon_ico.save(favicon_ico_path, 'ICO', sizes=[(16, 16), (32, 32)])

print("✅ Logo processing complete!")
PYTHON_SCRIPT
