#!/usr/bin/env bash
# Benchmark de las versiones C++ (serial, OpenMP, MPI).
# Escribe en outputs/times.csv (append) y outputs/metrics/.
#
# Uso (desde la raíz del repo):
#   bash tools/benchmark_cpp.sh [region ...]        # por defecto: amazonia pacifico
# Variables opcionales:
#   RUNS=5  SEED=12345  THREADS="1 2 4 8"  PROCS="1 2 4"
#
# Nota: no lance más hilos/procesos que núcleos FÍSICOS (guía §1.5); en una
# máquina de 4 núcleos, los 8 hilos de OpenMP quedan sobresuscritos.
set -euo pipefail
. "$(dirname "$0")/_equipo.sh"
cd "$(dirname "$0")/../cpp"
RUNS=${RUNS:-5}; SEED=${SEED:-12345}
THREADS=${THREADS:-"1 2 4 8"}; PROCS=${PROCS:-"1 2 4"}
REGIONS=${*:-"amazonia pacifico"}

[ -f ../data/GAM_regional_enriquecido.csv ] || python3 ../tools/export_csv.py
make -s all

for region in $REGIONS; do
  echo "=== $region ==="
  ./secuencial --region "$region" --runs "$RUNS" --seed "$SEED"
  for t in $THREADS; do ./openmp --region "$region" --threads "$t" --runs "$RUNS" --seed "$SEED"; done
  for p in $PROCS; do $MPIRUN -np "$p" ./mpi --region "$region" --runs "$RUNS" --seed "$SEED"; done
done
