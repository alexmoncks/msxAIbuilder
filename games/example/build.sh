#!/bin/sh
# Monta o exemplo. Rode da raiz do repositorio ou daqui -- tanto faz.
set -eu
raiz=$(cd "$(dirname "$0")/../.." && pwd)
cd "$raiz"
mkdir -p games/example/build
python3 -m msxasm games/example/game.asm \
    -o games/example/build/example.rom \
    --size 16K \
    -I games/example \
    --bank-map games/example/build/example.map
