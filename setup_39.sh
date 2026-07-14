#!/bin/bash
set -e

echo "Cleaning up old virtual environment..."
rm -rf venv39

echo "Creating new Python 3.9 virtual environment (venv39)..."
python3.9 -m venv venv39

echo "Upgrading pip, setuptools, and wheel..."
venv39/bin/pip install --upgrade pip setuptools wheel

echo "Installing project requirements..."
venv39/bin/pip install -r requirements-py39.txt

echo "Setup complete! You can now start the web app with:"
echo "./run_web.sh"
