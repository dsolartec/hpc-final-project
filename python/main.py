import argparse
import csv
import logging
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
from pathlib import Path
import time
from typing import Any, Optional

from adapters.utils_animations import ac_animate_boards
from adapters.utils_npcp import ac_apply_evolution_rules, ac_generate_initial_boards
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

def _initialize_pure(selected_region: Optional[str]):
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

        with open(f"../outputs/animations/pure_{region.lower()}.html", "w+") as file:
            file.write(ac_animate_boards(region, data))


def handle_pure(args: argparse.Namespace):
    logger.debug("=== Código ejecutándose en Python puro secuencial ===")
    region_arg = getattr(args, "region", "Pacifico")
    _initialize_pure(region_arg if region_arg.lower() != "todo" else None)


def _initialize_npcp(xp: Any, selected_region: Optional[str]):
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

        with open(f"../outputs/animations/{paradigm_name}_{region.lower()}.html", "w+") as file:
            file.write(ac_animate_boards(region, data))


def handle_numpy(args: argparse.Namespace):
    logger.debug("=== Código ejecutándose con NumPy ===")
    _initialize_npcp(np, args.region if args.region.lower() != "todo" else None)


def handle_cupy(args: argparse.Namespace):
    try:
        import cupy as cp

        # Verificar que CUDA realmente responda
        device_count = cp.cuda.runtime.getDeviceCount()
        if device_count == 0:
            raise Exception

        logger.debug("=== Código ejecutándose con CuPy ===")
        _initialize_npcp(cp, args.region if args.region.lower() != "todo" else None)
    except Exception:
        logger.error("CuPy no está instalado o no hay GPUs disponibles")


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
        "--region",
        choices=["amazonia", "andina", "caribe", "orinoquia", "pacifico", "todo"],
        default="Pacifico",
        help="Región seleccionada para ejecutar el modelo, por defecto: Pacifico",
        required=False,
        type=str,
    )
    parser_cupy.set_defaults(func=handle_cupy)

    # Initialize parser
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
