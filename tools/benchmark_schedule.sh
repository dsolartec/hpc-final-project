#!/usr/bin/env bash
# Efecto del scheduling de OpenMP (guía §6.3 y §6.7, pregunta 7).
# Escribe outputs/experiments/schedule/schedule.csv (region,schedule,threads,elapsed_time).
# Uso (desde la raíz del repo):  bash tools/benchmark_schedule.sh [region ...]   [RUNS=5 THREADS=4]
set -euo pipefail
cd "$(dirname "$0")/../cpp"
RUNS=${RUNS:-5}; THREADS=${THREADS:-4}; OUT=../outputs/experiments/schedule
REGIONS=${*:-"amazonia pacifico"}
make -s openmp
mkdir -p "$OUT"; rm -f "$OUT/times.csv"
echo "region,schedule,threads,elapsed_time" > "$OUT/schedule.csv"
for region in $REGIONS; do
  for s in static dynamic guided; do
    ./openmp --region "$region" --threads "$THREADS" --schedule "$s" --runs "$RUNS" --no-metrics --outdir "$OUT" \
      | grep -o 'elapsed=[0-9.]*' | cut -d= -f2 | sed "s/^/$region,$s,$THREADS,/" >> "$OUT/schedule.csv"
  done
done
cat "$OUT/schedule.csv" | tail -n +2 | awk -F, '{a[$1","$2]+=$4; n[$1","$2]++} END{for(k in a) printf "%s media=%.3f s\n", k, a[k]/n[k]}' | sort
