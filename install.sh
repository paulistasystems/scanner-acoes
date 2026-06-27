#!/bin/bash

# Stock Scanner - Installation Script
# This script sets up the virtual environment and installs dependencies

set -e

echo "🔧 Setting up Stock Scanner..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📥 Installing requirements..."
pip install -r requirements.txt

echo ""
echo "✨ Installation complete!"
echo ""
echo "To run the scanner:"
echo "  ./run_scanner.sh"
echo ""
echo "To activate the virtual environment manually:"
echo "  source venv/bin/activate"
