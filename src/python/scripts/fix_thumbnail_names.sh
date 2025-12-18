#!/bin/bash
# Script to add '_thumb' suffix to thumbnail files on Synology NAS

# 1. SET THIS to your actual thumbnails directory path on the NAS
TARGET_DIR="/volume1/docker/home-media-viewer/thumbnails"

if [ ! -d "$TARGET_DIR" ]; then
    echo "Error: Directory $TARGET_DIR not found."
    exit 1
fi

cd "$TARGET_DIR" || exit

echo "Scanning for .jpg files missing '_thumb' suffix in $TARGET_DIR..."

# Find all .jpg files (case-insensitive) that do NOT already end in _thumb.jpg
# This handles subdirectories recursively
find . -type f -iname "*.jpg" ! -iname "*_thumb.jpg" | while read -r file; do
    # Get the file path without the extension
    base="${file%.*}"
    
    # Rename to include _thumb.jpg (forcing lowercase extension to match DB)
    new_name="${base}_thumb.jpg"
    
    echo "Renaming: $file -> $new_name"
    mv "$file" "$new_name"
done

echo "Done!"
