#!/usr/bin/env bash
# Escalabilidad débil de MPI (guía §6.6, G6): el tamaño crece con el número de
# procesos manteniendo ~constantes las celdas por proceso (~1 900).
#   p=1 L=44 | p=2 L=62 | p=4 L=87 (= pacifico) | p=8 L=124 | p=10 L=138 | p=12 L=151 | p=16 L=175
# Solo se ejecutan las configuraciones con p <= núcleos físicos (o MAXP).
# Usa el argumento experimental --board-size con el clima de pacifico.
# Escribe en outputs/experiments/weak/times.csv (NO en outputs/times.csv).
# Uso (desde la raíz del repo):  bash tools/benchmark_weak.sh      [RUNS=5 MAXP=12]
set -euo pipefail
. "$(dirname "$0")/_equipo.sh"
cd "$(dirname "$0")/../cpp"
CORES=$(nucleos_fisicos)
RUNS=${RUNS:-5}; MAXP=${MAXP:-$CORES}; OUT=../outputs/experiments/weak
make -s mpi
rm -f "$OUT/times.csv"; mkdir -p "$OUT"
for cfg in "1 44" "2 62" "4 87" "8 124" "10 138" "12 151" "16 175"; do
  set -- $cfg
  [ "$1" -le "$MAXP" ] || continue
  $MPIRUN -np "$1" ./mpi --region pacifico --board-size "$2" --runs "$RUNS" --no-metrics --outdir "$OUT" | grep elapsed
done
