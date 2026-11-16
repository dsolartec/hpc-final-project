import argparse
import csv
import logging
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
from pathlib import Path
import random
import time
from typing import Any, Optional

from adapters.utils_animations import ac_animate_boards
from adapters.utils_npcp import ac_apply_evolution_rules, ac_generate_initial_boards
from adapters.utils_mp import ac_apply_evolution_rules as mp_apply_evolution_rules
from adapters.utils_parallel import DEFAULT_RUNS, DEFAULT_SEED, run_parallel_replicas
from adapters.utils_pure import (
    ac_apply_evolution_rules as pure_apply_evolution_rules,
    ac_generate_initial_boards as pure_generate_initial_boards,
)


# Increase the limit to 60 MB
plt.rcParams["animation.embed_limit"] = 100.0

# Configuración básica para mostrar mensajes en consola
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s'
)

logger = logging.getLogger("main")

# Datasets

df_by_regions = pd.read_parquet("../data/GAM_regional_enriquecido.parquet")
logger.debug(f"[DF] Tamaño del DataFrame (Por regiones): {len(df_by_regions)} datos")

# Handlers

def handle_pure(args: argparse.Namespace):
    logger.debug("=== Código ejecutándose en Python puro secuencial ===")
    selected_region = args.region if args.region.lower() != "todo" else None

    ac_data_store_by_regions = {}
    for region, new_df in df_by_regions.groupby("region"):
        if selected_region is not None and region.lower() != selected_region.lower():
            continue

        ac_data_store_by_regions[region] = {
            "df": new_df,
            **pure_generate_initial_boards(new_df),
        }

    for region, data in ac_data_store_by_regions.items():
        logger.info("[CELDAS] {0} celdas a analizar para la región {1}".format(
            (data["board_size"] ** 2) * 10 * 204,
            region,
        ))
    
    for region, data in ac_data_store_by_regions.items():
        start = time.perf_counter()
        pure_apply_evolution_rules(data["df"], data)
        elapsed = time.perf_counter() - start

        with open(f"../outputs/times.csv", "a") as times_csv_file:
            csv_writer = csv.writer(times_csv_file)
            csv_writer.writerow([
                time.time(), # execution_timestamp
                "python", # language
                "pure", # paradigm
                region.lower(), # region
                1, # workers
                data["board_size"], # board_size
                204, # iterations
                elapsed, # elapsed_time
            ])

        logger.info(f"[TIEMPO] Tiempo de ejecución para {region}: {elapsed:.2f} s")

        # Guardar series temporales para análisis y validación estadística
        metrics_dir = Path("../outputs/metrics")
        metrics_dir.mkdir(parents=True, exist_ok=True)
        if "simulation_history" in data:
            metrics_df = data["simulation_history"].copy()
            metrics_df.insert(0, "region", region.lower())
            metrics_df.insert(0, "paradigm", "pure")
            metrics_df.to_csv(metrics_dir / f"pure_{region.lower()}.csv", index=False)

        if not args.disable_animation:
            with open(f"../outputs/animations/pure_{region.lower()}.html", "w+") as file:
                file.write(ac_animate_boards(region, data))


def _initialize_npcp(xp: Any, selected_region: Optional[str], disable_animation: bool):
    ac_data_store_by_regions = {}
    for region, new_df in df_by_regions.groupby("region"):
        if selected_region is not None and region.lower() != selected_region.lower():
            continue

        ac_data_store_by_regions[region] = {
            "df": new_df,
            **ac_generate_initial_boards(xp, new_df),
        }

    for region, data in ac_data_store_by_regions.items():
        logger.info("[CELDAS] {0} celdas a analizar para la región {1}".format(
            (data["board_size"] ** 2) * 10 * 204,
            region,
        ))

    paradigm_name = xp.__name__.lower()
    for region, data in ac_data_store_by_regions.items():
        start = time.perf_counter()
        ac_apply_evolution_rules(xp, data["df"], data)
        elapsed = time.perf_counter() - start

        with open(f"../outputs/times.csv", "a") as times_csv_file:
            csv_writer = csv.writer(times_csv_file)
            csv_writer.writerow([
                time.time(), # execution_timestamp
                "python", # language
                paradigm_name, # paradigm
                region.lower(), # region
                1, # workers
                data["board_size"], # board_size
                204, # iterations
                elapsed, # elapsed_time
            ])

        logger.info(f"[TIEMPO] Tiempo de ejecución para {region}: {elapsed:.2f} s")

        # Guardar series temporales para análisis y validación estadística
        metrics_dir = Path("../outputs/metrics")
        metrics_dir.mkdir(parents=True, exist_ok=True)
        if "simulation_history" in data:
            metrics_df = data["simulation_history"].copy()
            metrics_df.insert(0, "region", region.lower())
            metrics_df.insert(0, "paradigm", paradigm_name)
            metrics_df.to_csv(metrics_dir / f"{paradigm_name}_{region.lower()}.csv", index=False)

        if not disable_animation:
            with open(f"../outputs/animations/{paradigm_name}_{region.lower()}.html", "w+") as file:
                file.write(ac_animate_boards(region, data))


def handle_numpy(args: argparse.Namespace):
    logger.debug("=== Código ejecutándose con NumPy ===")
    _initialize_npcp(np, args.region if args.region.lower() != "todo" else None, args.disable_animation)


def handle_cupy(args: argparse.Namespace):
    try:
        import cupy as cp

        # Verificar que CUDA realmente responda
        device_count = cp.cuda.runtime.getDeviceCount()
        if device_count == 0:
            raise Exception

        logger.debug("=== Código ejecutándose con CuPy ===")
        _initialize_npcp(cp, args.region if args.region.lower() != "todo" else None, args.disable_animation)
    except Exception:
        logger.error("CuPy no está instalado o no hay GPUs disponibles")


def handle_multiprocessing(args: argparse.Namespace):
    """
    Paralelo en CPU con multiprocessing. Dos estrategias:
      - replicas (por defecto): R réplicas Monte Carlo repartidas entre p procesos
        (adapters/utils_parallel.py; "nivel natural" según la guía, §5.6 paso 5).
      - franjas: una simulación repartida por franjas de filas entre p procesos con
        memoria compartida (adapters/utils_mp.py).
    """
    if args.estrategia == "franjas":
        handle_multiprocessing_franjas(args)
        return
    if args.runs is None:
        args.runs = DEFAULT_RUNS

    logger.debug("=== Código ejecutándose con multiprocessing (réplicas) ===")
    selected_region = args.region if args.region.lower() != "todo" else None

    for region, new_df in df_by_regions.groupby("region"):
        if selected_region is not None and region.lower() != selected_region.lower():
            continue

        logger.info(
            f"[MULTIPROCESSING] Región {region}: {args.runs} réplicas, "
            f"{args.workers} procesos, kernel {args.kernel}"
        )
        elapsed, results = run_parallel_replicas(
            new_df,
            workers=args.workers,
            runs=args.runs,
            seed=args.seed,
            kernel=args.kernel,
            keep_first_data=not args.disable_animation,
        )

        # Todo lo siguiente ocurre después de detener el cronómetro
        with open(f"../outputs/times.csv", "a") as times_csv_file:
            csv_writer = csv.writer(times_csv_file)
            csv_writer.writerow([
                time.time(), # execution_timestamp
                "python", # language
                "multiprocessing", # paradigm
                region.lower(), # region
                args.workers, # workers (procesos activos, exacto)
                results[0]["board_size"], # board_size
                204, # iterations
                elapsed, # elapsed_time (lote completo de réplicas)
            ])

        logger.info(
            f"[TIEMPO] Tiempo de ejecución para {region}: {elapsed:.2f} s "
            f"({args.runs} réplicas, {args.workers} procesos)"
        )

        metrics_dir = Path("../outputs/metrics")
        metrics_dir.mkdir(parents=True, exist_ok=True)
        for result in results:
            metrics_df = result["simulation_history"].copy()
            metrics_df.insert(0, "region", region.lower())
            metrics_df.insert(0, "paradigm", "multiprocessing")
            metrics_df.to_csv(
                metrics_dir / f"multiprocessing_{region.lower()}_run{result['run_id']}.csv",
                index=False,
            )

        if not args.disable_animation:
            with open(f"../outputs/animations/multiprocessing_{region.lower()}.html", "w+") as file:
                file.write(ac_animate_boards(region, results[0]["data"]))


def handle_multiprocessing_franjas(args: argparse.Namespace):
    """
    Descomposición de dominio: el tablero se reparte por franjas de filas entre p procesos
    persistentes que comparten memoria (SharedMemory) y se sincronizan con barreras.
    Cada réplica (--runs) es una simulación completa con semilla propia.
    """
    logger.debug("=== Código ejecutándose con multiprocessing (franjas de filas) ===")
    selected_region = args.region if args.region.lower() != "todo" else None
    requested_workers = args.workers if args.workers is not None else (os.cpu_count() or 1)
    runs = args.runs if args.runs is not None else 1
    paradigm = "multiprocessing_franjas"

    for region, new_df in df_by_regions.groupby("region"):
        if selected_region is not None and region.lower() != selected_region.lower():
            continue

        for run in range(runs):
            # Semillas: inicialización con seed + run; el worker k usa (seed + 1000 * run) + k,
            # de modo que réplicas distintas nunca comparten flujo aleatorio.
            init_rng = random.Random(args.seed + run)
            data = {"df": new_df, **pure_generate_initial_boards(new_df, rng=init_rng)}
            if run == 0:
                logger.info("[CELDAS] {0} celdas a analizar para la región {1}".format(
                    (data["board_size"] ** 2) * 10 * 204, region,
                ))

            mp_apply_evolution_rules(new_df, data, workers=requested_workers, seed=args.seed + 1000 * run)
            workers = data["workers"]  # Procesos efectivos (acotados al tamaño del tablero)
            elapsed = data["compute_time"]  # Excluye el arranque de procesos, I/O y renderizado

            # Todo lo siguiente ocurre después de detener el cronómetro
            with open(f"../outputs/times.csv", "a") as times_csv_file:
                csv_writer = csv.writer(times_csv_file)
                csv_writer.writerow([
                    time.time(), # execution_timestamp
                    "python", # language
                    paradigm, # paradigm
                    region.lower(), # region
                    workers, # workers (procesos efectivos, exacto)
                    data["board_size"], # board_size
                    204, # iterations
                    elapsed, # elapsed_time
                ])

            logger.info(
                f"[TIEMPO] Tiempo de ejecución para {region} con {workers} procesos (réplica {run}): {elapsed:.2f} s "
                f"(arranque de procesos: {data['setup_time']:.2f} s, no incluido)"
            )

            metrics_dir = Path("../outputs/metrics")
            metrics_dir.mkdir(parents=True, exist_ok=True)
            metrics_df = data["simulation_history"].copy()
            metrics_df.insert(0, "region", region.lower())
            metrics_df.insert(0, "paradigm", paradigm)
            sufijo = f"_run{run}" if runs > 1 else ""
            metrics_df.to_csv(metrics_dir / f"{paradigm}_{region.lower()}{sufijo}.csv", index=False)

            if run == 0 and not args.disable_animation:
                with open(f"../outputs/animations/{paradigm}_{region.lower()}.html", "w+") as file:
                    file.write(ac_animate_boards(region, data))


def main():
    times_csv_file = Path("../outputs/times.csv")
    if not times_csv_file.exists():
        with open("../outputs/times.csv", "w+") as times_csv_file:
            csv_writer = csv.writer(times_csv_file)
            csv_writer.writerow([
                "execution_timestamp",
                "language",
                "paradigm",
                "region",
                "workers",
                "board_size",
                "iterations",
                "elapsed_time"
            ])

    parser = argparse.ArgumentParser(description="CLI para el proyecto final de HPC")
    subparsers = parser.add_subparsers(
        dest="command",
        help="Comandos disponibles",
        required=True,
    )

    # Subcommand: Pure
    parser_pure = subparsers.add_parser(
        help="Ejecutar código puro (Secuencial)",
        name="pure",
    )
    parser_pure.add_argument(
        "--disable-animation",
        action=argparse.BooleanOptionalAction,
        help="No generar animación HTML",
        required=False,
    )
    parser_pure.add_argument(
        "--region",
        choices=["amazonia", "andina", "caribe", "orinoquia", "pacifico", "todo"],
        default="Pacifico",
        help="Región seleccionada para ejecutar el modelo, por defecto: Pacifico",
        required=False,
        type=str,
    )
    parser_pure.set_defaults(func=handle_pure)

    # Subcommand: NumPy
    parser_numpy = subparsers.add_parser(
        help="Ejecutar código con NumPy",
        name="numpy",
    )
    parser_numpy.add_argument(
        "--disable-animation",
        action=argparse.BooleanOptionalAction,
        help="No generar animación HTML",
        required=False,
    )
    parser_numpy.add_argument(
        "--region",
        choices=["amazonia", "andina", "caribe", "orinoquia", "pacifico", "todo"],
        default="Pacifico",
        help="Región seleccionada para ejecutar el modelo, por defecto: Pacifico",
        required=False,
        type=str,
    )
    parser_numpy.set_defaults(func=handle_numpy)

    # Subcommand: CuPy
    parser_cupy = subparsers.add_parser(
        help="Ejecutar código con CuPy",
        name="cupy",
    )
    parser_cupy.add_argument(
        "--disable-animation",
        action=argparse.BooleanOptionalAction,
        help="No generar animación HTML",
        required=False,
    )
    parser_cupy.add_argument(
        "--region",
        choices=["amazonia", "andina", "caribe", "orinoquia", "pacifico", "todo"],
        default="Pacifico",
        help="Región seleccionada para ejecutar el modelo, por defecto: Pacifico",
        required=False,
        type=str,
    )
    parser_cupy.set_defaults(func=handle_cupy)

    # Subcommand: multiprocessing (paralelo CPU)
    parser_mp = subparsers.add_parser(
        help="Ejecutar réplicas Monte Carlo en paralelo con multiprocessing",
        name="multiprocessing",
    )
    parser_mp.add_argument(
        "--disable-animation",
        action=argparse.BooleanOptionalAction,
        help="No generar animación HTML",
        required=False,
    )
    parser_mp.add_argument(
        "--region",
        choices=["amazonia", "andina", "caribe", "orinoquia", "pacifico", "todo"],
        default="Pacifico",
        help="Región seleccionada para ejecutar el modelo, por defecto: Pacifico",
        required=False,
        type=str,
    )
    parser_mp.add_argument(
        "--estrategia",
        choices=["replicas", "franjas"],
        default="replicas",
        help="replicas: R simulaciones independientes en paralelo (por defecto); "
             "franjas: una simulación repartida por filas con memoria compartida",
        required=False,
        type=str,
    )
    parser_mp.add_argument(
        "--workers",
        default=4,
        help="Cantidad de procesos de trabajo (p), por defecto: 4",
        required=False,
        type=int,
    )
    parser_mp.add_argument(
        "--runs",
        default=None,
        help=f"Cantidad de réplicas Monte Carlo (R), por defecto: {DEFAULT_RUNS} en replicas y 1 en franjas",
        required=False,
        type=int,
    )
    parser_mp.add_argument(
        "--seed",
        default=DEFAULT_SEED,
        help=f"Semilla base (la réplica k usa seed + k), por defecto: {DEFAULT_SEED}",
        required=False,
        type=int,
    )
    parser_mp.add_argument(
        "--kernel",
        choices=["numpy", "pure"],
        default="numpy",
        help="Implementación de cada réplica (solo estrategia replicas): numpy (por defecto) o pure",
        required=False,
        type=str,
    )
    parser_mp.set_defaults(func=handle_multiprocessing)

    # Initialize parser
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
