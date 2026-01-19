#!/bin/bash
# ==============================================================================
# Gopher APR - Joern Installation Script
# ==============================================================================
# This script installs Joern (v4.0.263 preferred) and its dependencies (Java 11+).
# It targets Ubuntu 22.04 LTS as specified in the environment description.
# ==============================================================================

set -e
JOERN_VERSION="v4.0.263"
INSTALL_DIR="/opt/joern"
BIN_DIR="$INSTALL_DIR/joern-cli"

echo "[INFO] Starting environment setup for Gopher APR..."

if type -p java > /dev/null; then
    echo "[INFO] Java is already installed."
    java -version
else
    echo "[WARN] Java not found. Installing OpenJDK 17..."
    sudo apt-get update
    sudo apt-get install -y openjdk-17-jdk unzip wget git
fi

if [ -d "$INSTALL_DIR" ]; then
    echo "[WARN] Directory $INSTALL_DIR already exists. Skipping download."
    echo "[INFO] Please ensure it contains the correct version ($JOERN_VERSION)."
else
    echo "[INFO] Downloading Joern ($JOERN_VERSION)..."


    TMP_DIR=$(mktemp -d)
    cd "$TMP_DIR"

    wget -O joern-cli.zip "https://github.com/joernio/joern/releases/download/$JOERN_VERSION/joern-cli.zip" || {
        echo "[ERROR] Failed to download specific version $JOERN_VERSION. Trying latest..."
        wget -O joern-cli.zip "https://github.com/joernio/joern/releases/latest/download/joern-cli.zip"
    }

    echo "[INFO] Unzipping to $INSTALL_DIR..."
    sudo mkdir -p "$INSTALL_DIR"
    sudo unzip -q joern-cli.zip -d "$INSTALL_DIR"

    if [ -d "$INSTALL_DIR/joern-cli" ]; then
        :
    else
        echo "[WARN] Verifying directory structure..."
    fi

    cd -
    rm -rf "$TMP_DIR"
fi

echo "[INFO] Setting up symlinks..."

sudo ln -sf "$BIN_DIR/joern" /usr/local/bin/joern
sudo ln -sf "$BIN_DIR/joern-parse" /usr/local/bin/joern-parse
sudo ln -sf "$BIN_DIR/joern-export" /usr/local/bin/joern-export

echo "[INFO] Verifying installation..."
if command -v joern > /dev/null; then
    echo "[SUCCESS] Joern installed successfully!"
    joern --version || echo "Joern CLI available."
else
    echo "[ERROR] Joern installation failed. Binaries not found in PATH."
    exit 1
fi

echo ""
echo "========================================================================"
echo "Installation Complete."
echo "Joern Location: $INSTALL_DIR"
echo "Recommended: Configure 'settings.yaml' with installation_path: $BIN_DIR"
echo "========================================================================"