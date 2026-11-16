#!/usr/bin/env bash
# Tiempos de Python puro y NumPy (una simulación por ejecución, workers=1).
# Python puro solo se mide en tableros pequeños (guía §1.2); el resto se extrapola en el notebook.
# Uso (desde la raíz del repo):  bash tools/benchmark_python_single.sh
# Variables: REPS=5  PURE_REPS=3  PURE_REGIONS="amazonia orinoquia"  NUMPY_REGIONS="amazonia orinoquia pacifico caribe andina"  PY=python3
set -euo pipefail
cd "$(dirname "$0")/../python"
REPS=${REPS:-5}; PURE_REPS=${PURE_REPS:-3}; PY=${PY:-python3}
PURE_REGIONS=${PURE_REGIONS:-"amazonia orinoquia"}
NUMPY_REGIONS=${NUMPY_REGIONS:-"amazonia orinoquia pacifico caribe andina"}
for region in $NUMPY_REGIONS; do
  $PY main.py numpy --region "$region" --disable-animation >/dev/null 2>&1  # calentamiento (queda registrado: descartar la 1.ª si se desea)
  for rep in $(seq "$REPS"); do $PY main.py numpy --region "$region" --disable-animation 2>&1 | grep TIEMPO; done
done
for region in $PURE_REGIONS; do
  for rep in $(seq "$PURE_REPS"); do $PY main.py pure --region "$region" --disable-animation 2>&1 | grep TIEMPO; done
done
