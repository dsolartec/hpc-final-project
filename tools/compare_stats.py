"""
Validación estadística entre implementaciones (AGENTS.md §9.2, criterios 2 y 3;
guía §5.7). Compara cada paradigma contra la referencia (por defecto `pure`).

Para cada región, paradigma y cepa, usando las réplicas *_run{id}.csv
(o el archivo único si no hay réplicas):
  * Tamaño epidémico final C = sum(nuevos_casos_mes) por réplica.
    Criterio 3:  |C_A - C_B| <= 2 * sqrt(SE_A^2 + SE_B^2),  SE = sd / sqrt(N).
  * IPA medio simulado (promedio sobre los 204 meses y las réplicas), con el
    mismo criterio de 2 errores estándar.
  * Criterio 2: fracción de meses en que la curva media de IPA del paradigma
    cae dentro de la banda mu_ref +- 2 sigma_ref de la referencia.

Uso (desde la raíz del repo):
    python tools/compare_stats.py [--reference pure] [--regions amazonia pacifico]
Escribe outputs/validation_summary.csv.
"""
import argparse
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
METRICS = ROOT / "outputs" / "metrics"
PATTERN = re.compile(r"^(?P<paradigm>[a-z_]+?)_(?P<region>amazonia|andina|caribe|orinoquia|pacifico)(?:_run(?P<run>\d+))?\.csv$")


def load_runs(metrics: Path = METRICS) -> dict[tuple[str, str], list[pd.DataFrame]]:
    groups: dict[tuple[str, str], dict[bool, list[pd.DataFrame]]] = {}
    for f in sorted(metrics.glob("*.csv")):
        m = PATTERN.match(f.name)
        if not m:
            continue
        key = (m["paradigm"], m["region"])
        groups.setdefault(key, {True: [], False: []})[m["run"] is not None].append(pd.read_csv(f))
    # Si hay réplicas _run{id}, se usan solo esas; si no, el archivo único.
    return {k: (v[True] or v[False]) for k, v in groups.items()}


def summarize(runs: list[pd.DataFrame], strain: str) -> dict:
    finals = np.array([r[f"{strain}_nuevos_casos_mes"].sum() for r in runs], dtype=float)
    ipa = np.vstack([r[f"IPA_{strain}_simulado"].to_numpy() for r in runs])  # (N, 204)
    ipa_mean_run = ipa.mean(axis=1)
    n = len(runs)
    se = lambda x: x.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan  # noqa: E731
    return {"n": n, "C_mean": finals.mean(), "C_se": se(finals),
            "ipa_mean": ipa_mean_run.mean(), "ipa_se": se(ipa_mean_run),
            "curve_mean": ipa.mean(axis=0), "curve_sd": ipa.std(axis=0, ddof=1) if n > 1 else np.zeros(ipa.shape[1])}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", default="pure")
    ap.add_argument("--regions", nargs="*")
    ap.add_argument("--metrics-dir", default=str(METRICS), help="carpeta con los CSV de métricas")
    a = ap.parse_args()
    groups = load_runs(Path(a.metrics_dir))
    rows = []
    for (paradigm, region), runs in sorted(groups.items()):
        if paradigm == a.reference or (a.regions and region not in a.regions):
            continue
        ref_runs = groups.get((a.reference, region))
        if not ref_runs:
            print(f"AVISO: falta la referencia {a.reference}_{region}; genere réplicas con tools/pure_replicas.py")
            continue
        for strain in ("falciparum", "vivax"):
            A, B = summarize(runs, strain), summarize(ref_runs, strain)
            tol_c = 2 * np.sqrt(A["C_se"] ** 2 + B["C_se"] ** 2)
            tol_i = 2 * np.sqrt(A["ipa_se"] ** 2 + B["ipa_se"] ** 2)
            band = np.mean(np.abs(A["curve_mean"] - B["curve_mean"]) <= 2 * B["curve_sd"] + 1e-12)
            rows.append({
                "region": region, "paradigm": paradigm, "reference": a.reference, "strain": strain,
                "n_paradigm": A["n"], "n_reference": B["n"],
                "C_final_mean": A["C_mean"], "C_final_se": A["C_se"],
                "C_final_ref_mean": B["C_mean"], "C_final_ref_se": B["C_se"],
                "C_final_diff": abs(A["C_mean"] - B["C_mean"]), "C_final_tol_2se": tol_c,
                "C_final_ok": bool(abs(A["C_mean"] - B["C_mean"]) <= tol_c),
                "IPA_mean": A["ipa_mean"], "IPA_ref_mean": B["ipa_mean"],
                "IPA_diff": abs(A["ipa_mean"] - B["ipa_mean"]), "IPA_tol_2se": tol_i,
                "IPA_ok": bool(abs(A["ipa_mean"] - B["ipa_mean"]) <= tol_i),
                "frac_months_in_ref_band": band,
            })
    if not rows:
        print("No hay pares para comparar.")
        return 1
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "outputs" / "validation_summary.csv", index=False)
    cols = ["region", "paradigm", "strain", "n_paradigm", "n_reference", "C_final_diff", "C_final_tol_2se",
            "C_final_ok", "IPA_mean", "IPA_ref_mean", "IPA_ok", "frac_months_in_ref_band"]
    with pd.option_context("display.width", 200, "display.float_format", "{:.3f}".format):
        print(out[cols].to_string(index=False))
    return 0 if (out["C_final_ok"] & out["IPA_ok"]).all() else 2


if __name__ == "__main__":
    sys.exit(main())
