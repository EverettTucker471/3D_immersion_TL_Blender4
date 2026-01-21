#!/bin/bash

echo "Launching Blender!"

# Source Conda's activation script (adjust the path if necessary)
source /home/everetttucker471/miniconda3/etc/profile.d/conda.sh

# Activate the Conda environment
conda activate blender-env

# Now, set the environment variables that Blender will inherit
export PYTHONPATH="$CONDA_PREFIX/lib/python3.11/site-packages:$PYTHONPATH"

# Also set the library path so that Blender can find shared libraries (like PDAL's)
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"

# Launch Blender
/opt/blender-4.5.3-linux-x64/blender "$@"