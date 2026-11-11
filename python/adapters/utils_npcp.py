from domain.constants import AC_BITING_RATE, AC_CELL_POPULATION, AC_MAX_MOSQUITOES_PER_CELL, AC_MOSQUITO_MAX_AGE_DAYS, AC_MOSQUITO_WEATHER_DENSITY, \
    AC_NEIGHBOR_COUPLING, AC_MOSQUITO_NEIGHBORS_DENSITY, AC_STEPS_PER_MONTH, AC_STRAIN_PARAMS
from domain.enums import MalariaType
import math
import numpy as np
import pandas as pd
from typing import Any


def ac_generate_initial_boards(
        xp: Any,
        df: Any,
):
    df_sorted = df.sort_values("fecha")
    df_by_date = df_sorted.groupby(["fecha"], sort=True)

    first_pop = float(df_by_date["poblacion_total"].sum().iloc[0])
    board_size = max(1, math.ceil(math.sqrt(first_pop / AC_CELL_POPULATION)))

    # Tomamos el promedio ponderado o media inicial de IPA (casos por cada 1.000 habitantes)
    IPA_falciparum = float(df_by_date["IPA_falciparum"].mean().iloc[0])
    IPA_vivax = float(df_by_date["IPA_vivax"].mean().iloc[0])

    p_init_falciparum = min(1.0, max(0.0, IPA_falciparum / float(AC_CELL_POPULATION)))
    p_init_vivax = min(1.0, max(0.0, IPA_vivax / float(AC_CELL_POPULATION)))

    # Humans - Falciparum (S + I + R = 1.000 por celda)
    humans_falciparum_infected_count_board = xp.random.binomial(
        n=AC_CELL_POPULATION,
        p=p_init_falciparum,
        size=(board_size, board_size),
    ).astype(xp.int32)
    humans_falciparum_recovered_count_board = xp.zeros((board_size, board_size), dtype=xp.int32)
    humans_falciparum_susceptible_count_board = (
        AC_CELL_POPULATION - humans_falciparum_infected_count_board
    ).astype(xp.int32)

    # Mosquitoes - Falciparum (Población basal inicial en equilibrio climático)
    init_mosq_total_f = xp.random.binomial(
        n=AC_MAX_MOSQUITOES_PER_CELL,
        p=0.25,
        size=(board_size, board_size),
    ).astype(xp.int32)
    mosquitoes_falciparum_infected_count_board = xp.random.binomial(
        n=init_mosq_total_f,
        p=min(1.0, p_init_falciparum * 2.0),
        size=(board_size, board_size),
    ).astype(xp.int32)
    mosquitoes_falciparum_susceptible_count_board = (
        init_mosq_total_f - mosquitoes_falciparum_infected_count_board
    ).astype(xp.int32)

    # Humans - Vivax (S + I + R = 1.000 por celda)
    humans_vivax_infected_count_board = xp.random.binomial(
        n=AC_CELL_POPULATION,
        p=p_init_vivax,
        size=(board_size, board_size),
    ).astype(xp.int32)
    humans_vivax_recovered_count_board = xp.zeros((board_size, board_size), dtype=xp.int32)
    humans_vivax_susceptible_count_board = (
        AC_CELL_POPULATION - humans_vivax_infected_count_board
    ).astype(xp.int32)

    # Mosquitoes - Vivax (Población basal inicial en equilibrio climático)
    init_mosq_total_v = xp.random.binomial(
        n=AC_MAX_MOSQUITOES_PER_CELL,
        p=0.25,
        size=(board_size, board_size),
    ).astype(xp.int32)
    mosquitoes_vivax_infected_count_board = xp.random.binomial(
        n=init_mosq_total_v,
        p=min(1.0, p_init_vivax * 2.0),
        size=(board_size, board_size),
    ).astype(xp.int32)
    mosquitoes_vivax_susceptible_count_board = (
        init_mosq_total_v - mosquitoes_vivax_infected_count_board
    ).astype(xp.int32)

    return {
        "board_size": board_size,
        "IPA_falciparum": IPA_falciparum,
        "IPA_vivax": IPA_vivax,
        "humans_falciparum_susceptible_count_board": humans_falciparum_susceptible_count_board,
        "humans_falciparum_infected_count_board": humans_falciparum_infected_count_board,
        "humans_falciparum_recovered_count_board": humans_falciparum_recovered_count_board,
        "mosquitoes_falciparum_susceptible_count_board": mosquitoes_falciparum_susceptible_count_board,
        "mosquitoes_falciparum_infected_count_board": mosquitoes_falciparum_infected_count_board,
        "humans_vivax_susceptible_count_board": humans_vivax_susceptible_count_board,
        "humans_vivax_infected_count_board": humans_vivax_infected_count_board,
        "humans_vivax_recovered_count_board": humans_vivax_recovered_count_board,
        "mosquitoes_vivax_susceptible_count_board": mosquitoes_vivax_susceptible_count_board,
        "mosquitoes_vivax_infected_count_board": mosquitoes_vivax_infected_count_board,
    }


def ac_count_neighbors(board: Any, xp: Any) -> Any:
    """
    Calcula la suma de los 8 vecinos de Moore en toda la cuadrícula 2D
    utilizando desplazamientos circulares (toroide) en GPU o CPU.

    Parameters:
        board: Tablero de conteos a analizar
        xp: Librería de NumPy o CuPy
    """

    int_board = board.astype(xp.int32)
    return (
        xp.roll(int_board,  1, axis=0) + xp.roll(int_board, -1, axis=0) +
        xp.roll(int_board,  1, axis=1) + xp.roll(int_board, -1, axis=1) +
        xp.roll(xp.roll(int_board,  1, axis=0),  1, axis=1) +
        xp.roll(xp.roll(int_board,  1, axis=0), -1, axis=1) +
        xp.roll(xp.roll(int_board, -1, axis=0),  1, axis=1) +
        xp.roll(xp.roll(int_board, -1, axis=0), -1, axis=1)
    )


def ac_to_numpy(arr: Any) -> np.ndarray:
    """Convierte un arreglo de CuPy o NumPy a np.ndarray en memoria de CPU."""

    if hasattr(arr, "get"):
        return arr.get()

    return np.asarray(arr)


def ac_fast_binomial(xp: Any, rng: Any, n: Any, p: Any) -> Any:
    """
    Muestreador Binomial vectorizado de alto rendimiento (aproximación Poisson para medias bajas
    y Gaussiana truncada en float32 para medias altas), evitando el cuello de botella de BTPE
    en tableros grandes (ej. Región Andina con 168x168 celdas).
    """

    mean = (n * p).astype(xp.float32)
    max_mean = float(xp.max(mean))
    if max_mean <= 0.0:
        return xp.zeros_like(n, dtype=xp.int32)

    if max_mean < 10.0:
        res = rng.poisson(xp.maximum(0.0, mean))
    else:
        std = xp.sqrt(xp.maximum(0.0, mean * (1.0 - p)))
        res = xp.rint(mean + std * rng.standard_normal(n.shape, dtype=xp.float32))

    return xp.clip(res, 0, n).astype(xp.int32)


def ac_step_strain_day(
        xp: Any,
        rng: Any,
        strain: MalariaType,
        S_h: Any,
        I_h: Any,
        R_h: Any,
        S_m: Any,
        I_m: Any,
        temperature: float,
        humidity: float,
        monthly_precipitation: float,
        dt_days: float = 1.0,
) -> tuple[Any, Any, Any, Any, Any, Any]:
    """
    Ejecuta un paso temporal (dt_days) del modelo metapoblacional SIRS (Humanos) - SI (Mosquitos)
    para una cepa específica (P. falciparum o P. vivax).
    Retorna los tableros actualizados (S_h, I_h, R_h, S_m, I_m) y los nuevos casos del sub-paso.
    """

    params = AC_STRAIN_PARAMS[strain]

    # 1. Factores climáticos de la cepa
    if params["t_min"] < temperature < 38.0:
        f_t = math.exp(-((temperature - params["t_opt"]) ** 2) / (2.0 * (params["t_sigma"] ** 2)))
    else:
        f_t = 0.0

    g_h = 1.0 / (1.0 + math.exp(-0.15 * (humidity - 65.0)))
    h_p = min(1.0, max(0.05, monthly_precipitation / 200.0))
    climate_suitability = f_t * g_h * h_p

    # 2. Conteo promedio de los 8 vecinos de Moore
    I_h_neighbors_mean = ac_count_neighbors(I_h, xp) / 8.0
    I_m_neighbors_mean = ac_count_neighbors(I_m, xp) / 8.0
    M_alive = S_m + I_m
    M_alive_neighbors_mean = ac_count_neighbors(M_alive, xp) / 8.0

    # 3. Exposición efectiva (acoplando la celda actual con sus 8 vecinos)
    I_m_effective = ((1.0 - AC_NEIGHBOR_COUPLING) * I_m + AC_NEIGHBOR_COUPLING * I_m_neighbors_mean) / float(AC_CELL_POPULATION)
    I_h_effective = ((1.0 - AC_NEIGHBOR_COUPLING) * I_h + AC_NEIGHBOR_COUPLING * I_h_neighbors_mean) / float(AC_CELL_POPULATION)

    # 4. Dinámica Humana (S -> I -> R -> S + recaídas en P. vivax) escalada por dt_days
    rate_m_to_h = max(0.0, min(1.0, AC_BITING_RATE * params["prob_mosquito_to_human"]))
    p_infect_human = xp.clip(1.0 - xp.power(1.0 - rate_m_to_h, I_m_effective * dt_days), 0.0, 1.0)
    p_recover_h = min(1.0, dt_days / params["recuperation_days"])
    p_loss_imm_h = min(1.0, dt_days / params["immunity_loss_days"])

    new_infected_h = ac_fast_binomial(xp, rng, S_h, p_infect_human)
    new_recovered_h = ac_fast_binomial(xp, rng, I_h, p_recover_h)

    if params["relapse_rate"] > 0.0:
        p_relapse = min(1.0, 1.0 - (1.0 - params["relapse_rate"]) ** dt_days)
        relapsed_h = ac_fast_binomial(xp, rng, R_h, p_relapse)
    else:
        relapsed_h = xp.zeros_like(R_h)

    remaining_R_h = xp.maximum(0, R_h - relapsed_h)
    lost_immunity_h = ac_fast_binomial(xp, rng, remaining_R_h, p_loss_imm_h)

    S_h_next = S_h - new_infected_h + lost_immunity_h
    I_h_next = I_h + new_infected_h - new_recovered_h + relapsed_h
    R_h_next = remaining_R_h + new_recovered_h - lost_immunity_h

    # 5. Dinámica del Mosquito (Nacimiento -> S_m -> I_m -> Muerte) escalada por dt_days
    p_death_m = min(1.0, dt_days / float(AC_MOSQUITO_MAX_AGE_DAYS))
    dead_S_m = ac_fast_binomial(xp, rng, S_m, p_death_m)
    dead_I_m = ac_fast_binomial(xp, rng, I_m, p_death_m)

    S_m_surv = S_m - dead_S_m
    I_m_surv = I_m - dead_I_m

    empty_m_slots = xp.maximum(0, AC_MAX_MOSQUITOES_PER_CELL - (S_m_surv + I_m_surv))
    p_emergence = AC_MOSQUITO_WEATHER_DENSITY * climate_suitability * dt_days
    p_dispersion = AC_MOSQUITO_NEIGHBORS_DENSITY * (M_alive_neighbors_mean / float(AC_MAX_MOSQUITOES_PER_CELL)) * dt_days
    p_birth_m = xp.clip(p_emergence + p_dispersion, 0.0, 1.0)

    newborn_m = ac_fast_binomial(xp, rng, empty_m_slots, p_birth_m)

    rate_h_to_m = max(0.0, min(1.0, AC_BITING_RATE * params["prob_human_to_mosquito"] * f_t))
    p_infect_mosquito = xp.clip(1.0 - xp.power(1.0 - rate_h_to_m, I_h_effective * dt_days), 0.0, 1.0)
    new_infected_m = ac_fast_binomial(xp, rng, S_m_surv, p_infect_mosquito)

    S_m_next = S_m_surv - new_infected_m + newborn_m
    I_m_next = I_m_surv + new_infected_m

    step_new_cases = new_infected_h + relapsed_h
    return S_h_next, I_h_next, R_h_next, S_m_next, I_m_next, step_new_cases


def ac_apply_evolution_rules(
        xp: Any,
        df: Any,
        ac_boards_data: Any,
) -> pd.DataFrame:
    """
    Evoluciona los tableros de P. falciparum y P. vivax a lo largo de las fechas del DataFrame,
    guardando tanto el historial numérico como las instantáneas 2D (frames_snapshots) para la animación.
    """

    rng = xp.random.default_rng()
    df_monthly = (
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

    total_cells = ac_boards_data["board_size"] ** 2

    # Estado actual Falciparum
    S_hf = ac_boards_data["humans_falciparum_susceptible_count_board"].copy()
    I_hf = ac_boards_data["humans_falciparum_infected_count_board"].copy()
    R_hf = ac_boards_data["humans_falciparum_recovered_count_board"].copy()
    S_mf = ac_boards_data["mosquitoes_falciparum_susceptible_count_board"].copy()
    I_mf = ac_boards_data["mosquitoes_falciparum_infected_count_board"].copy()

    # Estado actual Vivax
    S_hv = ac_boards_data["humans_vivax_susceptible_count_board"].copy()
    I_hv = ac_boards_data["humans_vivax_infected_count_board"].copy()
    R_hv = ac_boards_data["humans_vivax_recovered_count_board"].copy()
    S_mv = ac_boards_data["mosquitoes_vivax_susceptible_count_board"].copy()
    I_mv = ac_boards_data["mosquitoes_vivax_infected_count_board"].copy()

    history: list[dict[str, Any]] = []
    frames_snapshots: list[dict[str, Any]] = []

    for row in df_monthly.itertuples():
        days_in_month = float(pd.Timestamp(row.fecha).days_in_month)
        dt_days = days_in_month / float(AC_STEPS_PER_MONTH)
        temp = float(row.temperatura_media_Celsius)
        hum = float(row.humedad_mediana_pct)
        precip = float(row.precipitacion_media_mm)

        monthly_new_cases_f = 0
        monthly_new_cases_v = 0

        for _ in range(AC_STEPS_PER_MONTH):
            S_hf, I_hf, R_hf, S_mf, I_mf, new_f = ac_step_strain_day(
                xp, rng, MalariaType.FALCIPARUM, S_hf, I_hf, R_hf, S_mf, I_mf, temp, hum, precip, dt_days
            )
            S_hv, I_hv, R_hv, S_mv, I_mv, new_v = ac_step_strain_day(
                xp, rng, MalariaType.VIVAX, S_hv, I_hv, R_hv, S_mv, I_mv, temp, hum, precip, dt_days
            )
            monthly_new_cases_f += int(xp.sum(new_f))
            monthly_new_cases_v += int(xp.sum(new_v))

        frames_snapshots.append({
            "fecha": pd.Timestamp(row.fecha),
            "humans_falciparum_susceptible_count_board": ac_to_numpy(S_hf).copy(),
            "humans_falciparum_infected_count_board": ac_to_numpy(I_hf).copy(),
            "humans_falciparum_recovered_count_board": ac_to_numpy(R_hf).copy(),
            "mosquitoes_falciparum_susceptible_count_board": ac_to_numpy(S_mf).copy(),
            "mosquitoes_falciparum_infected_count_board": ac_to_numpy(I_mf).copy(),
            "humans_vivax_susceptible_count_board": ac_to_numpy(S_hv).copy(),
            "humans_vivax_infected_count_board": ac_to_numpy(I_hv).copy(),
            "humans_vivax_recovered_count_board": ac_to_numpy(R_hv).copy(),
            "mosquitoes_vivax_susceptible_count_board": ac_to_numpy(S_mv).copy(),
            "mosquitoes_vivax_infected_count_board": ac_to_numpy(I_mv).copy(),
        })

        history.append({
            "fecha": row.fecha,
            "falciparum_S_h": int(xp.sum(S_hf)),
            "falciparum_I_h": int(xp.sum(I_hf)),
            "falciparum_R_h": int(xp.sum(R_hf)),
            "falciparum_S_m": int(xp.sum(S_mf)),
            "falciparum_I_m": int(xp.sum(I_mf)),
            "falciparum_nuevos_casos_mes": monthly_new_cases_f,
            "IPA_falciparum_simulado": monthly_new_cases_f / float(total_cells),
            "IPA_falciparum_real": float(row.IPA_falciparum),
            "vivax_S_h": int(xp.sum(S_hv)),
            "vivax_I_h": int(xp.sum(I_hv)),
            "vivax_R_h": int(xp.sum(R_hv)),
            "vivax_S_m": int(xp.sum(S_mv)),
            "vivax_I_m": int(xp.sum(I_mv)),
            "vivax_nuevos_casos_mes": monthly_new_cases_v,
            "IPA_vivax_simulado": monthly_new_cases_v / float(total_cells),
            "IPA_vivax_real": float(row.IPA_vivax),
        })

    ac_boards_data["humans_falciparum_susceptible_count_board"] = S_hf
    ac_boards_data["humans_falciparum_infected_count_board"] = I_hf
    ac_boards_data["humans_falciparum_recovered_count_board"] = R_hf
    ac_boards_data["mosquitoes_falciparum_susceptible_count_board"] = S_mf
    ac_boards_data["mosquitoes_falciparum_infected_count_board"] = I_mf

    ac_boards_data["humans_vivax_susceptible_count_board"] = S_hv
    ac_boards_data["humans_vivax_infected_count_board"] = I_hv
    ac_boards_data["humans_vivax_recovered_count_board"] = R_hv
    ac_boards_data["mosquitoes_vivax_susceptible_count_board"] = S_mv
    ac_boards_data["mosquitoes_vivax_infected_count_board"] = I_mv

    df_sim = pd.DataFrame(history)
    ac_boards_data["simulation_history"] = df_sim
    ac_boards_data["frames_snapshots"] = frames_snapshots
    return df_sim
