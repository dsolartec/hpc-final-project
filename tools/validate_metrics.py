"""
Valida los CSV de métricas (AGENTS.md §9.1 y §9.2, criterio 1).

Por cada archivo outputs/metrics/*.csv comprueba:
  1. 204 filas.
  2. Las 18 columnas exactas, en el orden de AGENTS.md §9.1.
  3. Conservación humana por cepa: S_h + I_h + R_h == L^2 * 1000 en cada fila.
  4. Cota vectorial por cepa: 0 <= S_m + I_m <= 2000 * L^2 en cada fila.
  5. Valores no negativos y IPA_simulado == nuevos_casos_mes / L^2.

L se toma del tamaño por región de AGENTS.md §8.2 (derivado de la población inicial).

Uso (desde la raíz del repo):
    python tools/validate_metrics.py                      # todos los CSV de outputs/metrics
    python tools/validate_metrics.py outputs/metrics/serial_amazonia.csv ...
Sale con código 1 si algún archivo falla.
"""
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BOARD_SIZE = {"amazonia": 30, "orinoquia": 39, "pacifico": 87, "caribe": 96, "andina": 154}
COLUMNS = [
    "paradigm", "region", "fecha",
    "falciparum_S_h", "falciparum_I_h", "falciparum_R_h", "falciparum_S_m", "falciparum_I_m",
    "falciparum_nuevos_casos_mes", "IPA_falciparum_simulado", "IPA_falciparum_real",
    "vivax_S_h", "vivax_I_h", "vivax_R_h", "vivax_S_m", "vivax_I_m",
    "vivax_nuevos_casos_mes", "IPA_vivax_simulado", "IPA_vivax_real",
]


def check(path: Path) -> list[str]:
    errors: list[str] = []
    df = pd.read_csv(path)
    if list(df.columns) != COLUMNS:
        # AGENTS.md habla de "18 columnas" contando los datos; paradigm..IPA_vivax_real son 19 nombres.
        errors.append(f"columnas distintas a las esperadas: {list(df.columns)}")
        return errors
    if len(df) != 204:
        errors.append(f"{len(df)} filas (se esperaban 204)")
    regions = df["region"].unique()
    if len(regions) != 1 or regions[0] not in BOARD_SIZE:
        errors.append(f"región inválida: {regions}")
        return errors
    L = BOARD_SIZE[regions[0]]
    cells = L * L
    for s in ("falciparum", "vivax"):
        humans = df[f"{s}_S_h"] + df[f"{s}_I_h"] + df[f"{s}_R_h"]
        bad = (humans != cells * 1000).sum()
        if bad:
            errors.append(f"{s}: conservación humana falla en {bad} filas")
        mosq = df[f"{s}_S_m"] + df[f"{s}_I_m"]
        bad = ((mosq < 0) | (mosq > 2000 * cells)).sum()
        if bad:
            errors.append(f"{s}: cota de mosquitos falla en {bad} filas")
        cols = [f"{s}_S_h", f"{s}_I_h", f"{s}_R_h", f"{s}_S_m", f"{s}_I_m", f"{s}_nuevos_casos_mes"]
        if (df[cols] < 0).any().any():
            errors.append(f"{s}: hay conteos negativos")
        ipa = df[f"{s}_nuevos_casos_mes"] / cells
        if not (abs(ipa - df[f"IPA_{s}_simulado"]) < 1e-9).all():
            errors.append(f"{s}: IPA_simulado != nuevos_casos_mes / L^2")
    if not df["fecha"].is_monotonic_increasing:
        errors.append("las fechas no están en orden cronológico")
    return errors


def main(argv: list[str]) -> int:
    files = [Path(a) for a in argv] or sorted((ROOT / "outputs" / "metrics").glob("*.csv"))
    if not files:
        print("No hay CSV de métricas para validar.")
        return 1
    failed = 0
    for f in files:
        errs = check(f)
        status = "OK " if not errs else "FALLA"
        print(f"[{status}] {f.name}" + ("" if not errs else ": " + "; ".join(errs)))
        failed += bool(errs)
    print(f"\n{len(files) - failed}/{len(files)} archivos válidos")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
