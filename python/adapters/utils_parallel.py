
Paralelización en CPU con `multiprocessing` (paradigm="multiprocessing").

DISEÑO
------
Se paraleliza el ENSAMBLE Monte Carlo, no el interior de una simulación:
se ejecutan R réplicas independientes del modelo (por defecto R = 8) repartidas
entre p procesos de un `multiprocessing.Pool`. Cada réplica es una simulación
completa (inicialización + 204 meses) con su propia semilla.

¿Por qué réplicas y no franjas de filas con memoria compartida?
  * La guía (§1.3, P4) identifica dos patrones para este problema: el stencil
    sobre la malla (cubierto por OpenMP y MPI en C++) y los "ensambles de
    simulaciones independientes" (cubierto aquí).
  * La validación del proyecto es estadística (guía §5.7, AGENTS.md §9.2) y
    exige varias réplicas: el ensamble es trabajo que hay que hacer de todos
    modos, y es "vergonzosamente paralelo" (sin comunicación entre procesos).
  * En Python, repartir filas entre procesos obligaría a sincronizar 4 veces
    por mes tableros de pocos KB: el costo de comunicación entre procesos
    superaría al cómputo de cada franja en estos tamaños (L <= 154).

DEFINICIÓN DE SPEEDUP (importante para no falsear la comparación)
-----------------------------------------------------------------
`elapsed_time` es el tiempo de pared de las R réplicas con p procesos. El
baseline T_1 es EL MISMO R ejecutado con 1 proceso (`--workers 1`):
        S_p = T(R, 1) / T(R, p),      E_p = S_p / p
No se compara contra una sola simulación de `pure`/`numpy` (eso mezclaría el
tamaño del trabajo). Para comparar con otros paradigmas use elapsed_time / R.

SEMILLAS
--------
Réplica k usa la semilla `seed + k` (flujos distintos por réplica; repetir
semillas entre procesos produciría réplicas idénticas, error citado en la guía
§5.7).
  * kernel "pure":  random.Random(seed + k) -> totalmente reproducible.
  * kernel "numpy": np.random.seed(seed + k) fija la inicialización; el bucle
    temporal de utils_npcp crea su propio default_rng() sin semilla (entropía
    del sistema, independiente por proceso), así que las réplicas son
    independientes pero no reproducibles bit a bit.

MEDICIÓN
--------
El Pool se crea y se "calienta" (arranque de procesos e importaciones) ANTES de
iniciar el cronómetro; la escritura de CSV ocurre después de detenerlo.
"""
from multiprocessing import Pool
import random
import time
from typing import Any

import numpy as np
import pandas as pd

from adapters.utils_npcp import (
    ac_apply_evolution_rules as numpy_apply_evolution_rules,
    ac_generate_initial_boards as numpy_generate_initial_boards,
)
from adapters.utils_pure import (
    ac_apply_evolution_rules as pure_apply_evolution_rules,
    ac_generate_initial_boards as pure_generate_initial_boards,
)

DEFAULT_RUNS = 8
DEFAULT_SEED = 12345

_worker_df: pd.DataFrame | None = None


def _init_worker(df: pd.DataFrame) -> None:
    """Inicializador de cada proceso: recibe una sola vez los datos de la región."""
    global _worker_df
    _worker_df = df


def _noop(_: int) -> int:
    return 0


def run_replica(task: tuple[int, int, str, bool]) -> dict[str, Any]:
    """
    Ejecuta UNA réplica completa del modelo en el proceso trabajador.

    Parameters:
        task: (run_id, seed, kernel, keep_data). Si keep_data es True se devuelve
              también el diccionario completo (tableros y snapshots) para animar.
    """
    run_id, seed, kernel, keep_data = task
    df = _worker_df
    assert df is not None, "El proceso trabajador no fue inicializado"

    if kernel == "pure":
        rng = random.Random(seed + run_id)
        data = {"df": df, **pure_generate_initial_boards(df, rng=rng)}
        start = time.perf_counter()
        pure_apply_evolution_rules(df, data, rng=rng)
        sim_elapsed = time.perf_counter() - start
    else:
        np.random.seed(seed + run_id)
        data = {"df": df, **numpy_generate_initial_boards(np, df)}
        start = time.perf_counter()
        numpy_apply_evolution_rules(np, df, data)
        sim_elapsed = time.perf_counter() - start

    result: dict[str, Any] = {
        "run_id": run_id,
        "board_size": int(data["board_size"]),
        "simulation_history": data["simulation_history"],
        "sim_elapsed": sim_elapsed,
    }
    if keep_data:
        result["data"] = data
    return result


def run_parallel_replicas(
    df: pd.DataFrame,
    workers: int,
    runs: int = DEFAULT_RUNS,
    seed: int = DEFAULT_SEED,
    kernel: str = "numpy",
    keep_first_data: bool = False,
) -> tuple[float, list[dict[str, Any]]]:
    """
    Ejecuta `runs` réplicas independientes repartidas entre `workers` procesos.

    Returns:
        (elapsed, results): tiempo de pared del lote completo (segundos) y la
        lista de resultados ordenada por run_id.
    """
    tasks = [(run_id, seed, kernel, keep_first_data and run_id == 0) for run_id in range(runs)]
    with Pool(processes=workers, initializer=_init_worker, initargs=(df,)) as pool:
        pool.map(_noop, range(workers * 4))  # calentamiento: arranque de procesos (no cronometrado)

        start = time.perf_counter()
        # chunksize=1: reparto dinámico, cada proceso libre toma la siguiente réplica.
        results = list(pool.imap_unordered(run_replica, tasks, chunksize=1))
        elapsed = time.perf_counter() - start

    results.sort(key=lambda r: r["run_id"])
    return elapsed, results
