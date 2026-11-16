"""
Versión paralela en CPU del modelo SIRS - Ross-Macdonald usando `multiprocessing`.

Estrategia (descomposición de dominio por franjas de filas):

- Los tableros de ambas cepas viven en memoria compartida (`SharedMemory`) con doble
  búfer (estado actual / estado siguiente), de modo que ningún proceso copia tableros.
- El tablero L x L se parte en `p` franjas de filas contiguas, una por proceso.
  Cada proceso calcula SOLO sus filas del estado siguiente, leyendo además la fila
  vecina de cada borde (halo) del estado actual, con frontera periódica (toroide).
- Los procesos son persistentes: se crean una sola vez y se sincronizan con barreras
  (una por sub-paso semanal y otra por mes para que el proceso principal guarde la
  instantánea y las métricas). No se envían tableros por pipes en ningún momento.
- La lógica de cada celda es la misma de `utils_pure.ac_step_strain_day`.

Se expone en `main.py multiprocessing --estrategia franjas` (paradigm="multiprocessing_franjas").
La estrategia por defecto del proyecto es la de réplicas (adapters/utils_parallel.py), que es
la que la guía del curso señala como "nivel natural" para multiprocessing (§5.6, paso 5); esta
versión se conserva para comparar ambos esquemas, igual que la guía pide para MPI (paso 8).

Aleatoriedad: cada proceso usa su propio `random.Random(seed + rank)`. Con la misma
`seed` y el mismo número de procesos los resultados son reproducibles; con un número
de procesos distinto (o frente a la versión secuencial) las trayectorias estocásticas
difieren, aunque la dinámica agregada es equivalente (ver AGENTS.md §7).
"""

import logging
import random
import time
from multiprocessing import get_context
from multiprocessing.shared_memory import SharedMemory
from threading import BrokenBarrierError
from typing import Any, Optional

import numpy as np
import pandas as pd

from adapters.utils_pure import (
    ac_sample_binomial,
    calc_climate_suitability,
    calc_effective_exposure,
    calc_immunity_loss_probability,
    calc_infection_probability,
    calc_mosquito_birth_probability,
    calc_mosquito_death_probability,
    calc_recovery_probability,
    calc_relapse_probability,
)
from domain.constants import (
    AC_BITING_RATE,
    AC_MAX_MOSQUITOES_PER_CELL,
    AC_MOSQUITO_MAX_AGE_DAYS,
    AC_STEPS_PER_MONTH,
    AC_STRAIN_PARAMS,
)
from domain.enums import MalariaType


logger = logging.getLogger("utils_mp")

AC_STRAINS: tuple[MalariaType, ...] = (MalariaType.FALCIPARUM, MalariaType.VIVAX)

# Orden de los 5 tableros por cepa dentro del búfer compartido
_BOARD_ROLES: tuple[str, ...] = (
    "humans_{s}_susceptible_count_board",
    "humans_{s}_infected_count_board",
    "humans_{s}_recovered_count_board",
    "mosquitoes_{s}_susceptible_count_board",
    "mosquitoes_{s}_infected_count_board",
)
_S_H, _I_H, _R_H, _S_M, _I_M = range(5)

_DTYPE = np.int32

# Tiempo máximo de espera en las barreras del proceso principal. Si un worker muere (por
# ejemplo al arrancar), la barrera se rompe en vez de dejar el programa colgado para siempre.
_SETUP_TIMEOUT_S = 300.0
_MONTH_TIMEOUT_S = 1800.0


def _board_key(role: str, strain: MalariaType) -> str:
    return role.format(s=strain.value)


# ============================================================================
# 1. PASO DE SIMULACIÓN SOBRE UNA FRANJA DE FILAS (se ejecuta dentro de cada worker)
# ============================================================================


def _count_neighbors_local(ext: list[list[int]]) -> list[list[int]]:
    """
    Suma de los 8 vecinos de Moore para las filas locales de una franja.

    `ext` trae las filas de la franja más una fila de halo arriba y otra abajo
    (ya resueltas con frontera periódica), por lo que len(ext) = filas_locales + 2.
    Las columnas usan frontera periódica.
    """
    L = len(ext[0])
    result: list[list[int]] = []
    for i in range(1, len(ext) - 1):
        up, mid, down = ext[i - 1], ext[i], ext[i + 1]
        row = [0] * L
        for c in range(L):
            c_prev = c - 1  # c = 0 -> -1 apunta a la última columna (toroide)
            c_next = c + 1 if c + 1 < L else 0
            row[c] = (
                up[c_prev] + up[c] + up[c_next]
                + mid[c_prev] + mid[c_next]
                + down[c_prev] + down[c] + down[c_next]
            )
        result.append(row)
    return result


def _step_strain_rows(
    strain: MalariaType,
    cur: np.ndarray,
    nxt: np.ndarray,
    cases: np.ndarray,
    r0: int,
    r1: int,
    temperature: float,
    humidity: float,
    precipitation: float,
    dt_days: float,
    rng: Optional[random.Random],
) -> None:
    """
    Evoluciona las filas [r0, r1) de una cepa un sub-paso `dt_days`.

    Lee de `cur` (forma 5 x L x L, solo lectura) y escribe en `nxt` (5 x L x L) únicamente
    sus filas, y acumula los casos nuevos en `cases[r0:r1]` (L x L).
    """
    L = cur.shape[-1]
    params = AC_STRAIN_PARAMS[strain]

    climate_suitability, f_t = calc_climate_suitability(
        temperature, humidity, precipitation,
        params["t_min"], params["t_opt"], params["t_sigma"],
    )

    # Filas locales + halo (frontera periódica en filas)
    rows_idx = [r % L for r in range(r0 - 1, r1 + 1)]
    ext = [cur[k][rows_idx].tolist() for k in range(5)]

    I_h_neighbors = _count_neighbors_local(ext[_I_H])
    I_m_neighbors = _count_neighbors_local(ext[_I_M])
    m_alive_ext = [
        [s + i for s, i in zip(row_s, row_i)]
        for row_s, row_i in zip(ext[_S_M], ext[_I_M])
    ]
    M_alive_neighbors = _count_neighbors_local(m_alive_ext)

    # Probabilidades constantes del sub-paso
    rate_m_to_h = max(0.0, min(1.0, AC_BITING_RATE * params["prob_mosquito_to_human"]))
    p_recover_h = calc_recovery_probability(dt_days, params["recuperation_days"])
    p_loss_imm_h = calc_immunity_loss_probability(dt_days, params["immunity_loss_days"])
    p_relapse = calc_relapse_probability(dt_days, params["relapse_rate"])
    p_death_m = calc_mosquito_death_probability(dt_days, AC_MOSQUITO_MAX_AGE_DAYS)
    rate_h_to_m = max(0.0, min(1.0, AC_BITING_RATE * params["prob_human_to_mosquito"] * f_t))
    has_relapse = params["relapse_rate"] > 0.0

    n_rows = r1 - r0
    out = [[[0] * L for _ in range(n_rows)] for _ in range(5)]
    out_cases = [[0] * L for _ in range(n_rows)]

    for j in range(n_rows):
        sh_row, ih_row, rh_row = ext[_S_H][j + 1], ext[_I_H][j + 1], ext[_R_H][j + 1]
        sm_row, im_row = ext[_S_M][j + 1], ext[_I_M][j + 1]
        ih_neigh_row, im_neigh_row = I_h_neighbors[j], I_m_neighbors[j]
        m_alive_neigh_row = M_alive_neighbors[j]

        for c in range(L):
            s_h, i_h, r_h = sh_row[c], ih_row[c], rh_row[c]
            s_m, i_m = sm_row[c], im_row[c]

            i_m_eff = calc_effective_exposure(i_m, im_neigh_row[c] / 8.0)
            i_h_eff = calc_effective_exposure(i_h, ih_neigh_row[c] / 8.0)

            # Dinámica humana (S -> I -> R -> S, con recaídas en P. vivax)
            p_infect_h = calc_infection_probability(rate_m_to_h, i_m_eff, dt_days)
            new_infected_h = ac_sample_binomial(s_h, p_infect_h, rng)
            new_recovered_h = ac_sample_binomial(i_h, p_recover_h, rng)

            relapsed_h = ac_sample_binomial(r_h, p_relapse, rng) if has_relapse else 0
            remaining_r_h = max(0, r_h - relapsed_h)
            lost_immunity_h = ac_sample_binomial(remaining_r_h, p_loss_imm_h, rng)

            out[_S_H][j][c] = s_h - new_infected_h + lost_immunity_h
            out[_I_H][j][c] = i_h + new_infected_h - new_recovered_h + relapsed_h
            out[_R_H][j][c] = remaining_r_h + new_recovered_h - lost_immunity_h
            out_cases[j][c] = new_infected_h + relapsed_h

            # Dinámica del mosquito
            dead_s_m = ac_sample_binomial(s_m, p_death_m, rng)
            dead_i_m = ac_sample_binomial(i_m, p_death_m, rng)
            s_m_surv = s_m - dead_s_m
            i_m_surv = i_m - dead_i_m

            empty_m_slots = max(0, AC_MAX_MOSQUITOES_PER_CELL - (s_m_surv + i_m_surv))
            p_birth_m = calc_mosquito_birth_probability(
                climate_suitability,
                m_alive_neigh_row[c] / 8.0,
                dt_days,
            )
            newborn_m = ac_sample_binomial(empty_m_slots, p_birth_m, rng)

            p_infect_m = calc_infection_probability(rate_h_to_m, i_h_eff, dt_days)
            new_infected_m = ac_sample_binomial(s_m_surv, p_infect_m, rng)

            out[_S_M][j][c] = s_m_surv - new_infected_m + newborn_m
            out[_I_M][j][c] = i_m_surv + new_infected_m

    for k in range(5):
        nxt[k, r0:r1, :] = out[k]
    cases[r0:r1, :] += np.asarray(out_cases, dtype=_DTYPE)


def _worker_main(
    rank: int,
    r0: int,
    r1: int,
    state_name: str,
    cases_name: str,
    state_shape: tuple[int, ...],
    cases_shape: tuple[int, ...],
    schedule: list[tuple[float, float, float, float]],
    seed: Optional[int],
    ready_barrier: Any,
    step_barrier: Any,
    month_barrier: Any,
) -> None:
    """Proceso persistente: evoluciona su franja de filas durante toda la simulación."""
    state_shm = SharedMemory(name=state_name)
    cases_shm = SharedMemory(name=cases_name)
    state = cases = None
    try:
        state = np.ndarray(state_shape, dtype=_DTYPE, buffer=state_shm.buf)
        cases = np.ndarray(cases_shape, dtype=_DTYPE, buffer=cases_shm.buf)
        rng = random.Random(None if seed is None else seed + rank)

        ready_barrier.wait()

        t = 0  # sub-pasos completados; el estado actual está en el búfer t % 2
        for temperature, humidity, precipitation, dt_days in schedule:
            for _ in range(AC_STEPS_PER_MONTH):
                cur_buf = t % 2
                for s_idx, strain in enumerate(AC_STRAINS):
                    _step_strain_rows(
                        strain,
                        state[cur_buf, s_idx],
                        state[1 - cur_buf, s_idx],
                        cases[s_idx],
                        r0, r1,
                        temperature, humidity, precipitation, dt_days,
                        rng,
                    )
                step_barrier.wait()  # nadie lee el nuevo estado hasta que todos escriban
                t += 1

            month_barrier.wait()  # A: el principal toma la instantánea del mes
            month_barrier.wait()  # B: el principal terminó, se puede continuar
    except BrokenBarrierError:
        pass  # otro proceso falló; el principal reporta el error
    except BaseException:
        for barrier in (ready_barrier, step_barrier, month_barrier):
            barrier.abort()
        raise
    finally:
        del state, cases
        state_shm.close()
        cases_shm.close()


# ============================================================================
# 2. ORQUESTADOR (proceso principal)
# ============================================================================


def _monthly_schedule(df: pd.DataFrame) -> pd.DataFrame:
    """Misma agregación mensual que utils_pure.ac_apply_evolution_rules."""
    return (
        df.groupby("fecha", as_index=False)
        .agg({
            "temperatura_media_Celsius": "mean",
            "humedad_mediana_pct": "mean",
            "precipitacion_media_mm": "mean",
            "IPA_falciparum": "mean",
            "IPA_vivax": "mean",
            "falciparum": "sum",
            "vivax": "sum",
        })
        .sort_values("fecha")
        .reset_index(drop=True)
    )


def ac_apply_evolution_rules(
    df: pd.DataFrame,
    ac_boards_data: dict[str, Any],
    workers: int,
    seed: Optional[int] = None,
    start_method: str = "spawn",
) -> pd.DataFrame:
    """
    Equivalente paralelo de `utils_pure.ac_apply_evolution_rules(df, ac_boards_data)`.

    Parameters:
        df: DataFrame de la región (columnas de clima e IPA).
        ac_boards_data: Salida de `ac_generate_initial_boards` (tableros como listas anidadas).
        workers: Número de procesos solicitado (se limita a L, el número de filas del tablero).
        seed: Semilla base; el worker `rank` usa `seed + rank`. None = no reproducible.
        start_method: Método de arranque de procesos (`spawn` funciona en Linux, macOS y Windows).

    Al terminar rellena en `ac_boards_data` los 10 tableros finales, `simulation_history`,
    `frames_snapshots` y, además:
        - `workers`: procesos efectivos usados.
        - `setup_time`: segundos de arranque de procesos (excluido de `compute_time`).
        - `compute_time`: segundos de simulación, desde que todos los procesos están listos.
    """
    df_monthly = _monthly_schedule(df)
    L = int(ac_boards_data["board_size"])
    total_cells = L * L

    workers_eff = max(1, min(int(workers), L))
    if workers_eff != workers:
        logger.warning(f"[WORKERS] Se solicitaron {workers} procesos pero se usarán {workers_eff} (L={L})")

    bounds = [
        (int(chunk[0]), int(chunk[-1]) + 1)
        for chunk in np.array_split(np.arange(L), workers_eff)
    ]

    schedule = [
        (
            float(row.temperatura_media_Celsius),
            float(row.humedad_mediana_pct),
            float(row.precipitacion_media_mm),
            float(pd.Timestamp(row.fecha).days_in_month) / float(AC_STEPS_PER_MONTH),
        )
        for row in df_monthly.itertuples()
    ]

    state_shape = (2, len(AC_STRAINS), 5, L, L)  # [búfer, cepa, tablero, fila, columna]
    cases_shape = (len(AC_STRAINS), L, L)
    state_bytes = int(np.prod(state_shape)) * np.dtype(_DTYPE).itemsize
    cases_bytes = int(np.prod(cases_shape)) * np.dtype(_DTYPE).itemsize

    state_shm = SharedMemory(create=True, size=state_bytes)
    cases_shm = SharedMemory(create=True, size=cases_bytes)
    state = np.ndarray(state_shape, dtype=_DTYPE, buffer=state_shm.buf)
    cases = np.ndarray(cases_shape, dtype=_DTYPE, buffer=cases_shm.buf)
    state[:] = 0
    cases[:] = 0

    ctx = get_context(start_method)
    processes = []
    cur = final = None  # vistas sobre la memoria compartida (se liberan antes de cerrarla)
    history: list[dict[str, Any]] = []
    frames_snapshots: list[dict[str, Any]] = []

    try:
        # Estado inicial en el búfer 0
        for s_idx, strain in enumerate(AC_STRAINS):
            for k, role in enumerate(_BOARD_ROLES):
                state[0, s_idx, k] = np.asarray(ac_boards_data[_board_key(role, strain)], dtype=_DTYPE)

        ready_barrier = ctx.Barrier(workers_eff + 1)
        step_barrier = ctx.Barrier(workers_eff)
        month_barrier = ctx.Barrier(workers_eff + 1)

        setup_start = time.perf_counter()
        for rank, (r0, r1) in enumerate(bounds):
            process = ctx.Process(
                target=_worker_main,
                args=(
                    rank, r0, r1,
                    state_shm.name, cases_shm.name,
                    state_shape, cases_shape,
                    schedule, seed,
                    ready_barrier, step_barrier, month_barrier,
                ),
                daemon=True,
            )
            process.start()
            processes.append(process)

        ready_barrier.wait(timeout=_SETUP_TIMEOUT_S)
        compute_start = time.perf_counter()
        setup_time = compute_start - setup_start

        t = 0
        for row in df_monthly.itertuples():
            t += AC_STEPS_PER_MONTH
            month_barrier.wait(timeout=_MONTH_TIMEOUT_S)  # A: los workers terminaron el mes

            cur = state[t % 2]
            month_cases = [int(cases[s_idx].sum(dtype=np.int64)) for s_idx in range(len(AC_STRAINS))]
            cases[:] = 0

            snapshot: dict[str, Any] = {"fecha": pd.Timestamp(row.fecha)}
            record: dict[str, Any] = {"fecha": row.fecha}
            for s_idx, strain in enumerate(AC_STRAINS):
                name = strain.value
                boards = []
                for k, role in enumerate(_BOARD_ROLES):
                    board = cur[s_idx, k].copy()
                    snapshot[_board_key(role, strain)] = board
                    boards.append(int(board.sum(dtype=np.int64)))
                record[f"{name}_S_h"] = boards[_S_H]
                record[f"{name}_I_h"] = boards[_I_H]
                record[f"{name}_R_h"] = boards[_R_H]
                record[f"{name}_S_m"] = boards[_S_M]
                record[f"{name}_I_m"] = boards[_I_M]
                record[f"{name}_nuevos_casos_mes"] = month_cases[s_idx]
                record[f"IPA_{name}_simulado"] = month_cases[s_idx] / float(total_cells)
                record[f"IPA_{name}_real"] = float(getattr(row, f"IPA_{name}"))

            frames_snapshots.append(snapshot)
            history.append(record)

            month_barrier.wait(timeout=_MONTH_TIMEOUT_S)  # B: los workers pueden empezar el mes siguiente

        compute_time = time.perf_counter() - compute_start

        final = state[t % 2]
        for s_idx, strain in enumerate(AC_STRAINS):
            for k, role in enumerate(_BOARD_ROLES):
                ac_boards_data[_board_key(role, strain)] = final[s_idx, k].tolist()

        for process in processes:
            process.join(timeout=30)
        if any(p.exitcode not in (0, None) for p in processes):
            raise RuntimeError("Algún proceso worker terminó con error")

    except BrokenBarrierError as exc:
        caidos = [p.exitcode for p in processes if p.exitcode not in (0, None)]
        raise RuntimeError(
            "Un proceso worker falló o no respondió a tiempo "
            f"(códigos de salida: {caidos or 'ninguno terminó'}); revisa el traceback en la consola"
        ) from exc
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
            process.join()
        cur = final = None
        del state, cases
        state_shm.close()
        state_shm.unlink()
        cases_shm.close()
        cases_shm.unlink()

    # Orden de columnas igual al de la versión secuencial
    column_order = ["fecha"]
    for strain in AC_STRAINS:
        name = strain.value
        column_order += [
            f"{name}_S_h", f"{name}_I_h", f"{name}_R_h", f"{name}_S_m", f"{name}_I_m",
            f"{name}_nuevos_casos_mes", f"IPA_{name}_simulado", f"IPA_{name}_real",
        ]
    df_sim = pd.DataFrame(history)[column_order]

    ac_boards_data["simulation_history"] = df_sim
    ac_boards_data["frames_snapshots"] = frames_snapshots
    ac_boards_data["workers"] = workers_eff
    ac_boards_data["setup_time"] = setup_time
    ac_boards_data["compute_time"] = compute_time
    return df_sim
