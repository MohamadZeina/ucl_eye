#!/bin/bash
# Molecular Plus Plus Installation Script for Blender 4.5 (macOS)
# Usage: ./install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ADDON_NAME="molecular_plus"
BLENDER_VERSION="4.5"
BLENDER_ADDONS="$HOME/Library/Application Support/Blender/$BLENDER_VERSION/scripts/addons"
BLENDER_SITE_PACKAGES="/Applications/Blender $BLENDER_VERSION.app/Contents/Resources/$BLENDER_VERSION/python/lib/python3.11/site-packages"

echo "========================================"
echo "Molecular Plus Plus Installer"
echo "========================================"
echo ""
echo "Source directory: $SCRIPT_DIR"
echo "Addon destination: $BLENDER_ADDONS/$ADDON_NAME"
echo "Core module destination: $BLENDER_SITE_PACKAGES/molecular_core"
echo ""

# Check if Blender exists
if [ ! -d "/Applications/Blender $BLENDER_VERSION.app" ]; then
    echo "ERROR: Blender $BLENDER_VERSION not found at /Applications/Blender $BLENDER_VERSION.app"
    echo "Please install Blender $BLENDER_VERSION or modify BLENDER_VERSION in this script."
    exit 1
fi

# Check if compiled core module exists
if [ ! -d "$SCRIPT_DIR/c_sources/molecular_core" ]; then
    echo "ERROR: Compiled core module not found at $SCRIPT_DIR/c_sources/molecular_core"
    echo ""
    echo "Please compile first:"
    echo "  cd $SCRIPT_DIR/c_sources"
    echo "  /opt/homebrew/bin/python3.11 setup_arm64.py build_ext --inplace"
    exit 1
fi

# Create addon directory
echo "Creating addon directory..."
mkdir -p "$BLENDER_ADDONS/$ADDON_NAME"

# Copy Python files
echo "Copying Python addon files..."
cp "$SCRIPT_DIR"/*.py "$BLENDER_ADDONS/$ADDON_NAME/"

# Copy compiled core module
echo "Copying compiled core module..."
cp -r "$SCRIPT_DIR/c_sources/molecular_core" "$BLENDER_SITE_PACKAGES/"

echo ""
echo "========================================"
echo "Installation complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Open Blender $BLENDER_VERSION"
echo "2. Go to Edit > Preferences > Add-ons"
echo "3. Search for 'Molecular'"
echo "4. Enable 'Molecular Plus'"
echo ""
