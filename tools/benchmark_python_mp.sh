#!/usr/bin/env bash
# Benchmark de Python multiprocessing (réplicas Monte Carlo en paralelo).
# Uso (desde la raíz del repo):
#   bash tools/benchmark_python_mp.sh [region ...]     # por defecto: amazonia pacifico
# Variables: REPS=5 (repeticiones por configuración)  WORKERS="1 2 4 8"  RUNS=8  PY=python3
# T_1 del speedup = fila con workers=1 y el MISMO número de réplicas (RUNS).
# ESTRATEGIA=franjas mide en cambio la descomposición por filas (una simulación por ejecución,
# paradigm="multiprocessing_franjas"); su T_1 es la misma simulación con 1 proceso.
set -euo pipefail
cd "$(dirname "$0")/../python"
REPS=${REPS:-5}; WORKERS=${WORKERS:-"1 2 4 8"}; RUNS=${RUNS:-8}; PY=${PY:-python3}; ESTRATEGIA=${ESTRATEGIA:-replicas}
REGIONS=${*:-"amazonia pacifico"}
if [ "$ESTRATEGIA" = "franjas" ]; then
  for region in $REGIONS; do
    for w in $WORKERS; do
      $PY main.py multiprocessing --estrategia franjas --region "$region" --workers "$w" --runs "$REPS" --disable-animation 2>&1 | grep TIEMPO
    done
  done
  exit 0
fi
for region in $REGIONS; do
  $PY main.py multiprocessing --region "$region" --workers 1 --runs "$RUNS" --disable-animation >/dev/null 2>&1 || true  # calentamiento
  for w in $WORKERS; do
    for rep in $(seq "$REPS"); do
      $PY main.py multiprocessing --region "$region" --workers "$w" --runs "$RUNS" --disable-animation 2>&1 | grep TIEMPO
    done
  done
done
