"""
Convierte data/GAM_regional_enriquecido.parquet en data/GAM_regional_enriquecido.csv
con SOLO las columnas que usa el modelo (ver python/adapters/utils_pure.py):

- region, fecha (YYYY-MM-DD)
- poblacion_total            -> tamaño del tablero L (primera fecha)
- temperatura_media_Celsius  -> T
- humedad_mediana_pct        -> H
- precipitacion_media_mm     -> P
- IPA_falciparum, IPA_vivax  -> IPA inicial e IPA real
- falciparum, vivax          -> casos reales (informativo)
- dias_mes                   -> días del mes (dt = dias_mes / 4)

Los programas C++ solo leen este CSV (no dependen de Arrow/Parquet).

Uso (desde la raíz del repo):
    python tools/export_csv.py
"""
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "GAM_regional_enriquecido.parquet"
DST = ROOT / "data" / "GAM_regional_enriquecido.csv"

COLUMNS = [
    "region", "fecha", "poblacion_total",
    "temperatura_media_Celsius", "humedad_mediana_pct", "precipitacion_media_mm",
    "IPA_falciparum", "IPA_vivax", "falciparum", "vivax",
]


def main() -> int:
    df = pd.read_parquet(SRC)
    # Igual que utils_pure: una fila por (región, fecha); si hubiera varias se agregaría.
    out = (
        df.groupby(["region", "fecha"], as_index=False)
        .agg({
            "poblacion_total": "sum",
            "temperatura_media_Celsius": "mean",
            "humedad_mediana_pct": "mean",
            "precipitacion_media_mm": "mean",
            "IPA_falciparum": "mean",
            "IPA_vivax": "mean",
            "falciparum": "sum",
            "vivax": "sum",
        })
        .sort_values(["region", "fecha"])
        .reset_index(drop=True)
    )[COLUMNS]

    nulls = out.isna().sum()
    if nulls.any():
        print("ERROR: hay valores nulos en columnas del modelo:\n", nulls[nulls > 0])
        return 1

    out["dias_mes"] = pd.to_datetime(out["fecha"]).dt.days_in_month
    out["fecha"] = pd.to_datetime(out["fecha"]).dt.strftime("%Y-%m-%d")
    out.to_csv(DST, index=False)  # precisión completa (repr) para no alterar los datos
    counts = out.groupby("region").size().to_dict()
    print(f"Escrito {DST.relative_to(ROOT)}: {len(out)} filas, meses por región = {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
