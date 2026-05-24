#!/usr/bin/env bash
# Build the pyzbar Lambda Layer for Python 3.13 (Amazon Linux 2023, x86_64).
# Requires Docker. Output: pipeline/terraform/build/pyzbar_layer.zip
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/terraform/build"
LAYER_SRC="$BUILD_DIR/pyzbar_layer_src"
LAYER_ZIP="$BUILD_DIR/pyzbar_layer.zip"

mkdir -p "$BUILD_DIR"
rm -rf "$LAYER_SRC"
mkdir -p "$LAYER_SRC/python" "$LAYER_SRC/lib"

echo "==> Building in public.ecr.aws/lambda/python:3.13 container..."
docker run --rm \
  -v "$LAYER_SRC:/layer" \
  public.ecr.aws/lambda/python:3.13 \
  bash -c "
    set -e
    # Install zbar C library
    dnf install -y zbar zbar-libs 2>/dev/null || yum install -y zbar 2>/dev/null || true
    # Install Python packages into /layer/python
    pip install --quiet pyzbar Pillow -t /layer/python/
    # Copy the shared library to /layer/lib so Lambda finds it under /opt/lib (on LD_LIBRARY_PATH)
    find /usr /lib /lib64 -name 'libzbar.so*' 2>/dev/null | while IFS= read -r f; do
      cp -n \"\$f\" /layer/lib/ 2>/dev/null && echo \"  copied \$f\" || true
    done
    echo 'lib/ contents:' && ls /layer/lib/
  "

echo "==> Zipping layer..."
cd "$LAYER_SRC"
zip -r "$LAYER_ZIP" python/ lib/ -x '*.pyc' -x '*/__pycache__/*'
echo "==> Done: $LAYER_ZIP ($(du -sh "$LAYER_ZIP" | cut -f1))"
