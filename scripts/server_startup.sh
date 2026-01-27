#!/bin/bash

# Resolve the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Default to the named environment 'home-media'
# Adjust this path if your mamba/conda installation is different
ENV_NAME="home-media"

# Try to find conda/mamba
if [ -f "$HOME/miniforge3/etc/profile.d/conda.sh" ]; then
    . "$HOME/miniforge3/etc/profile.d/conda.sh"
elif [ -f "$HOME/mambaforge/etc/profile.d/conda.sh" ]; then
    . "$HOME/mambaforge/etc/profile.d/conda.sh"
elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    . "$HOME/anaconda3/etc/profile.d/conda.sh"
fi

# Activate the environment
conda activate $ENV_NAME || echo "Warning: Could not activate '$ENV_NAME'. Assuming python is in path or already active."

# Start the Server
# Note: Adjust workers based on CPU cores
echo "Starting Home Media Server from $PROJECT_ROOT..."
exec uvicorn src.python.main:app --host 0.0.0.0 --port 8000 --workers 4
