#!/bin/sh
cd `dirname $0`

# Create a virtual environment to run our code
VENV_NAME="venv"
PYTHON="$VENV_NAME/bin/python"

if ! $PYTHON -m pip install pyinstaller -Uqq; then
    exit 1
fi

# Build the Go binary
echo "Building Go orientation converter..."
cd orientation_converter
go build -o orientation_converter main.go
if [ $? -ne 0 ]; then
    echo "Failed to build Go binary"
    exit 1
fi
cd ..

# Copy the Go binary to a location where PyInstaller can find it
mkdir -p dist
cp orientation_converter/orientation_converter .

$PYTHON -m PyInstaller --onefile --hidden-import="googleapiclient" --add-binary="./orientation_converter:." src/main.py
tar -czvf dist/archive.tar.gz meta.json ./dist/main
