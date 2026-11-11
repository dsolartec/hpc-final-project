import argparse
import logging
import numpy as np
import pandas as pd
from typing import Any

from adapters.utils_npcp import ac_generate_initial_boards


# Configuración básica para mostrar mensajes en consola
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] [%(levelname)s] %(message)s'
)

logger = logging.getLogger(__name__)

# Datasets

df_by_regions = pd.read_parquet("../data/GAM_regional_enriquecido.parquet")
logger.debug(f"[DF] Tamaño del DataFrame (Por regiones): {len(df_by_regions)} datos")

df_by_departments = pd.read_parquet("../data/GAM_departamental_enriquecido.parquet")
logger.debug(f"[DF] Tamaño del DataFrame (Por departamentos): {len(df_by_departments)} datos")

df_by_cities = pd.read_parquet("../data/GAM_municipal_enriquecido.parquet")
logger.debug(f"[DF] Tamaño del DataFrame (Por municipios): {len(df_by_cities)} datos")

# Handlers

def handle_pure(args: argparse.Namespace):
    logger.debug("=== Código ejecutándose en Python puro secuencial ===")


def _initialize_npcp(xp: Any):
    ac_data_store_by_regions = {}
    for region, new_df in df_by_regions.groupby("region"):
        ac_data_store_by_regions[region] = {
            "df": new_df,
            **ac_generate_initial_boards(xp, new_df),
        }

    logger.debug("[CELDAS] {0} celdas a analizar para {1} regiones".format(
        sum((value["board_size"] ** 2) * 10 for value in ac_data_store_by_regions.values()),
        len(ac_data_store_by_regions.keys()),
    ))

    ac_data_store_by_departments = {}
    for department, new_df in df_by_departments.groupby("departamento"):
        ac_data_store_by_departments[department] = {
            "df": new_df,
            **ac_generate_initial_boards(xp, new_df),
        }

    logger.debug("[CELDAS] {0} celdas a analizar para {1} departamentos".format(
        sum((value["board_size"] ** 2) * 10 for value in ac_data_store_by_departments.values()),
        len(ac_data_store_by_departments.keys()),
    ))

    ac_data_store_by_cities = {}
    for city, new_df in df_by_cities.groupby("municipio"):
        ac_data_store_by_cities[city] = {
            "df": new_df,
            **ac_generate_initial_boards(xp, new_df),
        }

    logger.debug("[CELDAS] {0} celdas a analizar para {1} municipios".format(
        sum((value["board_size"] ** 2) * 10 for value in ac_data_store_by_cities.values()),
        len(ac_data_store_by_cities.keys()),
    ))


def handle_numpy(args: argparse.Namespace):
    logger.debug("=== Código ejecutándose con NumPy ===")
    _initialize_npcp(np)


def handle_cupy(args: argparse.Namespace):
    try:
        import cupy as cp

        # Verificar que CUDA realmente responda
        device_count = cp.cuda.runtime.getDeviceCount()
        if device_count == 0:
            raise Exception

        logger.debug("=== Código ejecutándose con CuPy ===")
        _initialize_npcp(cp)
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
    parser_numpy.set_defaults(func=handle_numpy)

    # Subcommand: CuPy
    parser_cupy = subparsers.add_parser(
        help="Ejecutar código con CuPy",
        name="cupy",
    )
    parser_cupy.set_defaults(func=handle_cupy)

    # Initialize parser
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
