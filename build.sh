#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> Building Linux site-packages for Python 3.9..."

# 1. Create clean build directory
BUILD_DIR="/tmp/scanner_linux_sitepackages"
if [ -d "$BUILD_DIR" ]; then
  trash "$BUILD_DIR"
fi
mkdir -p "$BUILD_DIR"

# 2. Download wheels (if not already downloaded)
WHEELS_DIR="/tmp/scanner_wheels"
if [ ! -d "$WHEELS_DIR" ] || [ -z "$(ls -A $WHEELS_DIR 2>/dev/null)" ]; then
  echo "   Downloading wheels..."
  mkdir -p "$WHEELS_DIR"
  /usr/bin/python3 -m pip download \
    --platform manylinux_2_17_x86_64 \
    --python-version 3.9 \
    --only-binary=:all: \
    --dest "$WHEELS_DIR" \
    -r requirements-py39.txt
else
  echo "   Using cached wheels: $WHEELS_DIR"
fi

# 3. Install into build directory (Linux x86_64 platform)
echo "   Installing Linux wheels into $BUILD_DIR..."
/usr/bin/python3 -m pip install \
  --no-index --find-links "$WHEELS_DIR" \
  --target "$BUILD_DIR" \
  --platform manylinux_2_17_x86_64 \
  --python-version 3.9 \
  --only-binary=:all: \
  -r requirements-py39.txt

echo "   Build complete: $(ls $BUILD_DIR | wc -l | tr -d ' ') packages ($(du -sh $BUILD_DIR | awk '{print $1}'))"
echo "   Ready for deploy."
