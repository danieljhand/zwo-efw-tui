#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# install_sdk.sh
#
# Copies the correct EFW SDK shared library for the current macOS platform
# into the project's local lib/ directory.
#
# Usage:
#   ./scripts/install_sdk.sh <path-to-extracted-sdk>
#
# Example:
#   ./scripts/install_sdk.sh ~/Downloads/EFW_linux_mac_SDK_V1.8.4
#
# The script expects the extracted SDK to contain an efw/lib/ subdirectory
# as distributed by ZWO:
#   efw/lib/mac_arm64/libEFWFilter.dylib
#   efw/lib/mac_x64/libEFWFilter.dylib
#
# Download the SDK from: https://releaselog.zwoastro.com/efw
# -----------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ---------------------------------------------------------------------------
# Check argument
# ---------------------------------------------------------------------------

SDK_ROOT="${1:-}"
if [[ -z "$SDK_ROOT" ]]; then
    echo "Error: no SDK path provided."
    echo ""
    echo "Usage:    $0 <path-to-extracted-sdk>"
    echo "Example:  $0 ~/Downloads/EFW_linux_mac_SDK_V1.8.4"
    echo ""
    echo "Download the SDK from: https://releaselog.zwoastro.com/efw"
    exit 1
fi

# Resolve to absolute path
SDK_ROOT="$(cd "$SDK_ROOT" && pwd)"

# ---------------------------------------------------------------------------
# Locate the SDK lib/ directory
# ---------------------------------------------------------------------------

SDK_LIB=""
for candidate in "$SDK_ROOT/efw/lib" "$SDK_ROOT/lib"; do
    if [[ -d "$candidate" ]]; then
        SDK_LIB="$candidate"
        break
    fi
done

if [[ -z "$SDK_LIB" ]]; then
    echo "Error: cannot find the SDK lib/ directory."
    echo "  Tried: $SDK_ROOT/efw/lib"
    echo "  Tried: $SDK_ROOT/lib"
    echo ""
    echo "Ensure you pass the root of the extracted SDK archive."
    exit 1
fi

# ---------------------------------------------------------------------------
# Platform check — macOS only
# ---------------------------------------------------------------------------

OS="$(uname -s)"
ARCH="$(uname -m)"

if [[ "$OS" != "Darwin" ]]; then
    echo "Error: $OS is not yet supported."
    echo "  This project currently supports macOS (arm64 and x86_64) only."
    exit 1
fi

if [[ "$ARCH" == "arm64" ]]; then
    SRC_DIR="mac_arm64"
else
    SRC_DIR="mac_x64"
fi

# ---------------------------------------------------------------------------
# Copy library
# ---------------------------------------------------------------------------

SRC="$SDK_LIB/$SRC_DIR/libEFWFilter.dylib"

if [[ ! -f "$SRC" ]]; then
    echo "Error: library not found at $SRC"
    echo "  Check that the SDK archive was fully extracted."
    exit 1
fi

DEST_DIR="$PROJECT_DIR/lib/$SRC_DIR"
mkdir -p "$DEST_DIR"
cp "$SRC" "$DEST_DIR/libEFWFilter.dylib"
echo "✓  Copied: $DEST_DIR/libEFWFilter.dylib"

# ---------------------------------------------------------------------------
# macOS Gatekeeper — remove quarantine and apply an ad-hoc signature
#
# Libraries extracted from a downloaded archive carry a quarantine extended
# attribute that causes macOS to block them at load time. Stripping it and
# re-signing with an ad-hoc identity (-) allows Python's ctypes to load the
# library without needing a Developer ID certificate.
# ---------------------------------------------------------------------------

echo "  Removing quarantine attribute ..."
xattr -cr "$DEST_DIR/libEFWFilter.dylib"

echo "  Applying ad-hoc code signature ..."
codesign --force --deep --sign - "$DEST_DIR/libEFWFilter.dylib"

echo "✓  Library ready: $DEST_DIR/libEFWFilter.dylib"
echo ""
echo "Next: install Python dependencies."
echo "  python3 -m venv env"
echo "  source env/bin/activate"
echo "  pip install -r requirements.txt"
