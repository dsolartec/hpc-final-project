"""
Genera N réplicas Monte Carlo SEMBRADAS de la referencia Python puro
(python/adapters/utils_pure.py, sin modificarlo) para la validación estadística
de AGENTS.md §9.2.

¿Por qué existe? `main.py pure` usa el generador global sin semilla y escribe
una sola réplica (pure_{region}.csv); con una sola realización no se puede
calcular un error estándar. Este script llama a las MISMAS funciones de
utils_pure con un random.Random(seed + run) por réplica.

Salida: outputs/metrics/pure_{region}_run{id}.csv (mismo formato que main.py).
NO escribe en times.csv: las réplicas se ejecutan en paralelo para ahorrar
tiempo, así que su duración no es una medición válida de la versión pura.

Uso (desde la raíz del repo):
    python tools/pure_replicas.py --region amazonia --runs 8 --jobs 4
"""
import argparse
from multiprocessing import Pool
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "python"))

import pandas as pd  # noqa: E402

from adapters.utils_pure import ac_apply_evolution_rules, ac_generate_initial_boards  # noqa: E402

REGION_NAMES = {"amazonia": "Amazonia", "andina": "Andina", "caribe": "Caribe",
                "orinoquia": "Orinoquia", "pacifico": "Pacifico"}


def one_replica(task: tuple[str, int, int]) -> str:
    region, run, seed = task
    df = pd.read_parquet(ROOT / "data" / "GAM_regional_enriquecido.parquet")
    df = df[df["region"] == REGION_NAMES[region]]
    rng = random.Random(seed + run)
    data = {"df": df, **ac_generate_initial_boards(df, rng=rng)}
    t0 = time.perf_counter()
    ac_apply_evolution_rules(df, data, rng=rng)
    elapsed = time.perf_counter() - t0
    out = data["simulation_history"].copy()
    out.insert(0, "region", region)
    out.insert(0, "paradigm", "pure")
    path = ROOT / "outputs" / "metrics" / f"pure_{region}_run{run}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
    return f"{path.name} ({elapsed:.1f} s)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--region", choices=list(REGION_NAMES), required=True)
    ap.add_argument("--runs", type=int, default=8)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--first-run", type=int, default=0, help="id de la primera réplica (para añadir más)")
    ap.add_argument("--jobs", type=int, default=4, help="réplicas simultáneas (procesos)")
    a = ap.parse_args()
    tasks = [(a.region, run, a.seed) for run in range(a.first_run, a.first_run + a.runs)]
    with Pool(a.jobs) as pool:
        for msg in pool.imap_unordered(one_replica, tasks):
            print("escrito", msg, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
