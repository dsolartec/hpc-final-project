#!/usr/bin/env bash
# =============================================================================
# Ejecuta TODO el experimento de CPU en este equipo, de principio a fin:
#   datos -> compilación -> benchmarks -> validación -> notebook -> informe -> presentación
#
# Uso (desde la raíz del repo):
#   bash tools/run_all.sh              # medición completa (~1 h en 12 núcleos)
#   RAPIDO=1 bash tools/run_all.sh     # prueba rápida (~5 min): solo amazonia, 2 repeticiones
#
# Variables opcionales:
#   PY=python3               intérprete para main.py. Active ANTES el entorno del proyecto
#                            (ver ENTREGA_PARA_DANIEL.md, "Preparación")
#   PYTOOLS=python3          intérprete para tools/ y el notebook (necesita pandas, matplotlib, jupyter)
#   WORKERS="1 2 4 8 10"     lista de hilos/procesos (por defecto se calcula con los núcleos FÍSICOS)
#   RUNS=5                   repeticiones por configuración (la guía pide al menos 5)
#   LIMPIAR=1                borra outputs/times.csv y métricas anteriores antes de medir (por defecto 1)
#
# No lanza más hilos/procesos que núcleos físicos (guía §1.5). CuPy/CUDA NO se ejecutan
# aquí (TODO Daniel): sus filas se añaden después a outputs/times.csv y se repite el paso 6.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
. tools/_equipo.sh
PY=${PY:-python3}; PYTOOLS=${PYTOOLS:-python3}; RUNS=${RUNS:-5}; LIMPIAR=${LIMPIAR:-1}
CORES=$(nucleos_fisicos)
if [ -z "${WORKERS:-}" ]; then
  WORKERS=""; for w in 1 2 4 8 12 16 24 32; do [ "$w" -le "$CORES" ] && WORKERS="$WORKERS $w"; done
  case " $WORKERS " in *" $CORES "*) ;; *) WORKERS="$WORKERS $CORES";; esac
fi
MAXW=$(echo $WORKERS | tr ' ' '\n' | sort -n | tail -1)
REG_ESCALA="amazonia pacifico"; REG_RESTO="orinoquia caribe andina"; PURE_RUNS_A=24; PURE_RUNS_P=8
REG_ESCALA_FRANJAS="amazonia pacifico"   # franjas usa el núcleo de Python puro: es la parte más lenta
if [ "${RAPIDO:-0}" = "1" ]; then RUNS=2; REG_ESCALA="amazonia"; REG_RESTO=""; PURE_RUNS_A=4; PURE_RUNS_P=0; REG_ESCALA_FRANJAS="amazonia"; fi
paso() { echo; echo "=== [$(date +%H:%M:%S)] $* ==="; }

paso "0. Equipo: $CORES núcleos físicos ($(nucleos_rendimiento) de alto rendimiento); workers = $WORKERS; repeticiones = $RUNS"
mkdir -p outputs/metrics outputs/animations outputs/experiments
if [ "$LIMPIAR" = "1" ]; then rm -f outputs/times.csv outputs/metrics/*.csv outputs/experiments/times_cpp_glibc_lgamma.csv; fi
bash tools/hardware_info.sh > outputs/hardware.txt; cat outputs/hardware.txt

paso "1. Datos y compilación"
$PYTOOLS tools/export_csv.py
make -C cpp -s clean all openmp_glibc_lgamma

paso "2. C++: serial, OpenMP y MPI (escalabilidad fuerte en: $REG_ESCALA)"
RUNS=$RUNS THREADS="$WORKERS" PROCS="$WORKERS" bash tools/benchmark_cpp.sh $REG_ESCALA
[ -n "$REG_RESTO" ] && RUNS=$RUNS THREADS="$MAXW" PROCS="$MAXW" bash tools/benchmark_cpp.sh $REG_RESTO

paso "3. Experimentos: escalabilidad débil, scheduling y lgamma"
RUNS=$RUNS MAXP=$MAXW bash tools/benchmark_weak.sh
RUNS=$RUNS THREADS=$MAXW bash tools/benchmark_schedule.sh $REG_ESCALA
TMP=outputs/experiments/_lgamma_tmp; rm -rf "$TMP"
for region in $REG_ESCALA; do for t in $WORKERS; do
  (cd cpp && ./openmp_glibc_lgamma --region "$region" --threads "$t" --runs "$RUNS" --no-metrics --outdir "../$TMP" | grep elapsed)
done; done
mv "$TMP/times.csv" outputs/experiments/times_cpp_glibc_lgamma.csv; rm -rf "$TMP"

paso "4. Python: NumPy, puro y multiprocessing (réplicas y franjas)"
if [ "${RAPIDO:-0}" = "1" ]; then
  PY="$PY" REPS=$RUNS PURE_REPS=1 PURE_REGIONS="amazonia" NUMPY_REGIONS="amazonia" bash tools/benchmark_python_single.sh
else
  PY="$PY" REPS=$RUNS bash tools/benchmark_python_single.sh
fi
PY="$PY" REPS=$RUNS WORKERS="$WORKERS" bash tools/benchmark_python_mp.sh $REG_ESCALA
PY="$PY" REPS=$RUNS WORKERS="$WORKERS" ESTRATEGIA=franjas bash tools/benchmark_python_mp.sh $REG_ESCALA_FRANJAS

paso "5. Validación"
$PYTOOLS tools/pure_replicas.py --region amazonia --runs $PURE_RUNS_A --jobs "$CORES"
[ "$PURE_RUNS_P" -gt 0 ] && $PYTOOLS tools/pure_replicas.py --region pacifico --runs $PURE_RUNS_P --jobs "$CORES"
$PYTOOLS tools/validate_metrics.py | tail -1
$PYTOOLS tools/compare_stats.py || true   # código 2 = algún criterio de 2 SE no se cumple (ver informe §6.2)

paso "6. Notebook, informe y presentación"
$PYTOOLS -m jupyter execute --inplace notebooks/analisis.ipynb
$PYTOOLS tools/build_informe.py
$PYTOOLS tools/build_presentacion.py

paso "LISTO. Revise: outputs/figures/, informe.pdf, docs/presentacion.pptx y docs/CHECKLIST_REVISION.md"
