import argparse
import logging
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import time
from typing import Any, Optional

from adapters.utils_animations import ac_animate_boards
from adapters.utils_npcp import ac_apply_evolution_rules, ac_generate_initial_boards


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

    for region, data in ac_data_store_by_regions.items():
        start = time.perf_counter()
        ac_apply_evolution_rules(xp, data["df"], data)
        elapsed = time.perf_counter() - start

        logger.info(f"[TIEMPO] Tiempo de ejecución para {region}: {elapsed} s")

        with open(f"../outputs/animations/{xp.__name__.lower()}_{region.lower()}.html", "w+") as file:
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
