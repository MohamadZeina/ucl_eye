#!/bin/bash
set -e
cd /tmp
rm -rf molecular_build 2>/dev/null || true
mkdir -p molecular_build/molecular_core

cp /home/mo/github/ucl_eye/publication_galaxy_claude/molecular-plus/c_sources/*.pyx /tmp/molecular_build/
cp /home/mo/github/ucl_eye/publication_galaxy_claude/molecular-plus/c_sources/__init__.py /tmp/molecular_build/molecular_core/

cd /tmp/molecular_build
cat simulate.pyx update.pyx init.pyx links.pyx spatial_hash.pyx collide.pyx memory.pyx utils.pyx structures.pyx relax.pyx > molecular_core/core.pyx
echo "Concatenated pyx files"

/home/mo/.local/bin/cython -3 molecular_core/core.pyx -o molecular_core/core.c
echo "Cython done"

gcc -shared -fPIC -O3 -mavx2 -ffast-math -fno-builtin -fopenmp \
    -I/home/mo/anaconda3/include/python3.11 \
    molecular_core/core.c \
    -o molecular_core/core.cpython-311-x86_64-linux-gnu.so \
    -lm -fopenmp
echo "GCC done"

# Install to Blender
cp -r /tmp/molecular_build/molecular_core /home/mo/Applications/blender-4.5.5-linux-x64/4.5/python/lib/python3.11/site-packages/
echo "Installed to Blender"

# Update backup
cp /tmp/molecular_build/molecular_core/core.cpython-311-x86_64-linux-gnu.so \
   /home/mo/github/ucl_eye/publication_galaxy_claude/molecular-plus/compiled_backups/core_ubuntu2204_x64_20260122_b520b23.so
echo "Backup updated"

echo "SUCCESS"
