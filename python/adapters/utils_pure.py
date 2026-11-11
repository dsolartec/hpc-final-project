import math
import pandas as pd
import random
from typing import Any, Optional

from domain.constants import (
    AC_BITING_RATE,
    AC_CELL_POPULATION,
    AC_MAX_MOSQUITOES_PER_CELL,
    AC_MOSQUITO_MAX_AGE_DAYS,
    AC_MOSQUITO_NEIGHBORS_DENSITY,
    AC_MOSQUITO_WEATHER_DENSITY,
    AC_NEIGHBOR_COUPLING,
    AC_STEPS_PER_MONTH,
    AC_STRAIN_PARAMS,
)
from domain.enums import MalariaType


# ============================================================================
# 1. FUNCIONES MATEMÁTICAS FUNDAMENTALES DEL MODELO SIRS - ROSS-MACDONALD
# ============================================================================


def calc_thermal_factor(
    temperature: float,
    t_min: float,
    t_opt: float,
    t_sigma: float,
) -> float:
    """
    Factor térmico de desarrollo extrínseco (esporogonia) del parásito f_s(T):
    f_s(T) = exp(- (T - T_opt)^2 / (2 * sigma_T^2))  si  T_min < T < 38.0 °C
             0                                        en otro caso

    Parameters:
        temperature: Temperatura media ambiental (°C).
        t_min: Umbral térmico inferior para la esporogonia (°C).
        t_opt: Temperatura óptima de transmisión (°C).
        t_sigma: Amplitud o tolerancia térmica (°C).

    Returns:
        Factor normalizado f_s(T) en el intervalo [0.0, 1.0].
    """
    if t_min < temperature < 38.0:
        return math.exp(-((temperature - t_opt) ** 2) / (2.0 * (t_sigma ** 2)))
    return 0.0


def calc_humidity_factor(humidity: float) -> float:
    """
    Factor sigmoidal de humedad relativa g(H) que modula la supervivencia
    del vector Anopheles adulto:
    g(H) = 1.0 / (1.0 + exp(-0.15 * (H - 65.0)))

    Parameters:
        humidity: Humedad relativa en porcentaje (%).

    Returns:
        Factor sigmoidal en el intervalo (0.0, 1.0).
    """
    return 1.0 / (1.0 + math.exp(-0.15 * (humidity - 65.0)))


def calc_precipitation_factor(precipitation: float) -> float:
    """
    Factor lineal truncado h(P) que modula la disponibilidad de criaderos
    y charcas larvarias:
    h(P) = min(1.0, max(0.05, P / 200.0))

    Parameters:
        precipitation: Precipitación mensual acumulada (mm).

    Returns:
        Factor de criaderos en el intervalo [0.05, 1.0].
    """
    return min(1.0, max(0.05, precipitation / 200.0))


def calc_climate_suitability(
    temperature: float,
    humidity: float,
    precipitation: float,
    t_min: float,
    t_opt: float,
    t_sigma: float,
) -> tuple[float, float]:
    """
    Calcula el índice compuesto de idoneidad climática Phi_s(T, H, P) y
    el factor térmico f_s(T):
    Phi_s(T, H, P) = f_s(T) * g(H) * h(P)

    Returns:
        tuple (climate_suitability, f_t)
    """
    f_t = calc_thermal_factor(temperature, t_min, t_opt, t_sigma)
    g_h = calc_humidity_factor(humidity)
    h_p = calc_precipitation_factor(precipitation)
    suitability = f_t * g_h * h_p
    return suitability, f_t


def calc_effective_exposure(
    local_val: float,
    neighbor_mean: float,
    coupling: float = AC_NEIGHBOR_COUPLING,
    population: float = AC_CELL_POPULATION,
) -> float:
    """
    Calcula la densidad efectiva de exposición infecciosa con acoplamiento
    espacial hacia los 8 vecinos de Moore, normalizada por habitante de celda:
    I_eff = ((1 - alpha) * I_local + alpha * I_vecinos_mean) / N_H

    Parameters:
        local_val: Conteo de individuos infecciosos en la celda actual.
        neighbor_mean: Promedio de individuos infecciosos en las 8 celdas vecinas.
        coupling: Coeficiente de acoplamiento espacial (alpha).
        population: Población humana base por celda (N_H = 1.000).
    """
    return ((1.0 - coupling) * local_val + coupling * neighbor_mean) / float(population)


def calc_infection_probability(
    contact_rate: float,
    effective_exposure: float,
    dt_days: float,
) -> float:
    """
    Probabilidad de infección durante un sub-paso dt_days derivada del proceso
    de escape estocástico (proceso de Poisson / geométrico continuo):
    p_inf = 1.0 - (1.0 - contact_rate)^(effective_exposure * dt_days)

    Parameters:
        contact_rate: Tasa de contacto infectivo efectivo r = a * b (acotada a [0, 1]).
        effective_exposure: Exposición efectiva normalizada I_eff.
        dt_days: Duración del sub-paso de simulación en días.
    """
    rate = max(0.0, min(1.0, contact_rate))
    exponent = effective_exposure * dt_days
    if exponent <= 0.0 or rate <= 0.0:
        return 0.0
    if rate >= 1.0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - math.pow(1.0 - rate, exponent)))


def calc_recovery_probability(dt_days: float, recuperation_days: float) -> float:
    """
    Probabilidad de recuperación clínica humana (I -> R) en un intervalo dt_days:
    p_rec = min(1.0, dt_days / tau_rec)
    """
    if recuperation_days <= 0.0:
        return 1.0
    return min(1.0, max(0.0, dt_days / recuperation_days))


def calc_immunity_loss_probability(dt_days: float, immunity_loss_days: float) -> float:
    """
    Probabilidad de pérdida de inmunidad temporal humana (R -> S) en un intervalo dt_days:
    p_loss = min(1.0, dt_days / tau_imm)
    """
    if immunity_loss_days <= 0.0:
        return 1.0
    return min(1.0, max(0.0, dt_days / immunity_loss_days))


def calc_relapse_probability(dt_days: float, relapse_rate: float) -> float:
    """
    Probabilidad de recaída hepática por reactivación de hipnozoítos latentes
    (R -> I), exclusiva de Plasmodium vivax:
    p_relapse = min(1.0, 1.0 - (1.0 - rho_relapse)^dt_days)
    """
    if relapse_rate <= 0.0:
        return 0.0
    rate = min(1.0, max(0.0, relapse_rate))
    return min(1.0, max(0.0, 1.0 - math.pow(1.0 - rate, dt_days)))


def calc_mosquito_death_probability(
    dt_days: float,
    max_age_days: float = AC_MOSQUITO_MAX_AGE_DAYS,
) -> float:
    """
    Probabilidad de mortalidad natural del mosquito vector en dt_days:
    p_death = min(1.0, dt_days / tau_vida_m)
    """
    if max_age_days <= 0.0:
        return 1.0
    return min(1.0, max(0.0, dt_days / float(max_age_days)))


def calc_mosquito_birth_probability(
    climate_suitability: float,
    alive_neighbors_mean: float,
    dt_days: float,
    weather_density: float = AC_MOSQUITO_WEATHER_DENSITY,
    neighbors_density: float = AC_MOSQUITO_NEIGHBORS_DENSITY,
    max_mosquitoes: float = AC_MAX_MOSQUITOES_PER_CELL,
) -> float:
    """
    Probabilidad de emergencia climática y dispersión vecinal de nuevos mosquitos
    susceptibles por slot vacío en la celda:
    p_birth = clip((beta_clima * Phi_s + beta_vecinos * (M_vecinos / K_M)) * dt_days, 0.0, 1.0)
    """
    p_emergence = weather_density * climate_suitability * dt_days
    p_dispersion = neighbors_density * (alive_neighbors_mean / float(max_mosquitoes)) * dt_days
    return max(0.0, min(1.0, p_emergence + p_dispersion))


# ============================================================================
# 2. OPERACIONES SOBRE MATRICES 2D EN PYTHON PURO (LISTAS ANIDADAS)
# ============================================================================


def create_empty_board(board_size: int, fill_value: int = 0) -> list[list[int]]:
    """Crea una cuadrícula L x L inicializada con un valor constante en Python puro."""
    return [[fill_value for _ in range(board_size)] for _ in range(board_size)]


def copy_board(board: list[list[int]]) -> list[list[int]]:
    """Copia superficial rápida por filas de una cuadrícula 2D (evita deepcopy)."""
    return [row[:] for row in board]


def sum_board(board: list[list[int]]) -> int:
    """Calcula la suma total de elementos en una matriz 2D de Python puro."""
    return sum(sum(row) for row in board)


def ac_count_neighbors(board: list[list[int]]) -> list[list[int]]:
    """
    Calcula la suma de los 8 vecinos de Moore en toda la cuadrícula 2D
    utilizando condiciones de frontera periódicas (toroide 2D) en Python puro.

    N_Moore(X)_{i,j} = sum_{(dr, dc) != (0,0)} X_{(i+dr) % L, (j+dc) % L}
    """
    L = len(board)
    neighbors = [[0] * L for _ in range(L)]
    for r in range(L):
        r_prev = (r - 1) % L
        r_next = (r + 1) % L
        row_prev = board[r_prev]
        row_curr = board[r]
        row_next = board[r_next]
        for c in range(L):
            c_prev = (c - 1) % L
            c_next = (c + 1) % L
            neighbors[r][c] = (
                row_prev[c_prev] + row_prev[c] + row_prev[c_next] +
                row_curr[c_prev]               + row_curr[c_next] +
                row_next[c_prev] + row_next[c] + row_next[c_next]
            )
    return neighbors


# ============================================================================
# 3. MUESTREADOR ESTOCÁSTICO ESCALAR EN PYTHON PURO
# ============================================================================


def ac_sample_binomial(
    n: int,
    p: float,
    rng: Optional[random.Random] = None,
) -> int:
    """
    Muestreador Binomial escalar en Python puro.

    - Si n <= 0 o p <= 0: retorna 0 en O(1).
    - Si p >= 1: retorna n en O(1).
    - En Python 3.12+, utiliza `random.binomialvariate` implementado en C para máxima velocidad.
    - Como fallback, implementa la aproximación Normal/Poisson según AGENTS.md §7.1.
    """
    if n <= 0 or p <= 0.0:
        return 0
    if p >= 1.0:
        return int(n)

    r = rng if rng is not None else random
    if hasattr(r, "binomialvariate"):
        return r.binomialvariate(int(n), float(p))

    # Fallback aproximación asintótica continua (AGENTS.md §7.1)
    mean = n * p
    if mean < 10.0:
        # Algoritmo de Poisson (Knuth)
        L = math.exp(-mean)
        k = 0
        p_val = 1.0
        rand_fn = r.random if rng is not None else random.random
        while p_val > L:
            k += 1
            p_val *= rand_fn()
        return min(int(n), max(0, k - 1))
    else:
        # Aproximación Normal truncada
        std = math.sqrt(mean * (1.0 - p))
        gauss_fn = r.gauss if rng is not None else random.gauss
        sample = gauss_fn(mean, std)
        return min(int(n), max(0, round(sample)))


# ============================================================================
# 4. PASO DE SIMULACIÓN SUB-MENSUAL Y REGLAS DE EVOLUCIÓN
# ============================================================================


def ac_step_strain_day(
    *args,
    **kwargs,
) -> tuple[
    list[list[int]],
    list[list[int]],
    list[list[int]],
    list[list[int]],
    list[list[int]],
    list[list[int]],
]:
    """
    Ejecuta un sub-paso temporal (dt_days) del modelo metapoblacional
    SIRS (Humanos) - SI (Mosquitos) para una cepa específica (P. falciparum o P. vivax)
    completamente en Python puro sin dependencias de NumPy.

    Soporta dos firmas para compatibilidad:
    - Firma pura:
        ac_step_strain_day(strain, S_h, I_h, R_h, S_m, I_m, temperature, humidity,
                           monthly_precipitation, dt_days=1.0, rng=None)
    - Firma compatible con utils_npcp:
        ac_step_strain_day(xp, rng, strain, S_h, I_h, R_h, S_m, I_m, temperature,
                           humidity, monthly_precipitation, dt_days=1.0)
    """
    # Desempaquetado polimórfico de argumentos
    if len(args) >= 3 and isinstance(args[2], MalariaType):
        # Firma (xp, rng, strain, S_h, I_h, R_h, S_m, I_m, temp, hum, precip, dt_days)
        rng = args[1]
        strain = args[2]
        S_h, I_h, R_h, S_m, I_m = args[3], args[4], args[5], args[6], args[7]
        temp = args[8]
        hum = args[9]
        precip = args[10]
        dt_days = args[11] if len(args) > 11 else kwargs.get("dt_days", 1.0)
    else:
        # Firma pura directa
        strain = args[0] if len(args) > 0 else kwargs["strain"]
        S_h = args[1] if len(args) > 1 else kwargs["S_h"]
        I_h = args[2] if len(args) > 2 else kwargs["I_h"]
        R_h = args[3] if len(args) > 3 else kwargs["R_h"]
        S_m = args[4] if len(args) > 4 else kwargs["S_m"]
        I_m = args[5] if len(args) > 5 else kwargs["I_m"]
        temp = args[6] if len(args) > 6 else kwargs["temperature"]
        hum = args[7] if len(args) > 7 else kwargs["humidity"]
        precip = args[8] if len(args) > 8 else kwargs["monthly_precipitation"]
        dt_days = args[9] if len(args) > 9 else kwargs.get("dt_days", 1.0)
        rng = kwargs.get("rng", None)

    L = len(S_h)
    params = AC_STRAIN_PARAMS[strain]

    # 1. Factores climáticos e idoneidad
    climate_suitability, f_t = calc_climate_suitability(
        temp, hum, precip,
        params["t_min"], params["t_opt"], params["t_sigma"]
    )

    # 2. Conteo de los 8 vecinos de Moore (condiciones de frontera periódicas)
    I_h_neighbors = ac_count_neighbors(I_h)
    I_m_neighbors = ac_count_neighbors(I_m)

    M_alive = [[S_m[r][c] + I_m[r][c] for c in range(L)] for r in range(L)]
    M_alive_neighbors = ac_count_neighbors(M_alive)

    # 3. Probabilidades constantes para el sub-paso
    rate_m_to_h = max(0.0, min(1.0, AC_BITING_RATE * params["prob_mosquito_to_human"]))
    p_recover_h = calc_recovery_probability(dt_days, params["recuperation_days"])
    p_loss_imm_h = calc_immunity_loss_probability(dt_days, params["immunity_loss_days"])
    p_relapse = calc_relapse_probability(dt_days, params["relapse_rate"])
    p_death_m = calc_mosquito_death_probability(dt_days, AC_MOSQUITO_MAX_AGE_DAYS)
    rate_h_to_m = max(0.0, min(1.0, AC_BITING_RATE * params["prob_human_to_mosquito"] * f_t))

    # 4. Tableros de salida para t + dt
    S_h_next = create_empty_board(L, 0)
    I_h_next = create_empty_board(L, 0)
    R_h_next = create_empty_board(L, 0)
    S_m_next = create_empty_board(L, 0)
    I_m_next = create_empty_board(L, 0)
    step_new_cases = create_empty_board(L, 0)

    # 5. Evolución celda por celda
    for r in range(L):
        sh_row = S_h[r]
        ih_row = I_h[r]
        rh_row = R_h[r]
        sm_row = S_m[r]
        im_row = I_m[r]

        ih_neigh_row = I_h_neighbors[r]
        im_neigh_row = I_m_neighbors[r]
        m_alive_neigh_row = M_alive_neighbors[r]

        sh_next_row = S_h_next[r]
        ih_next_row = I_h_next[r]
        rh_next_row = R_h_next[r]
        sm_next_row = S_m_next[r]
        im_next_row = I_m_next[r]
        cases_row = step_new_cases[r]

        for c in range(L):
            s_h = sh_row[c]
            i_h = ih_row[c]
            r_h = rh_row[c]
            s_m = sm_row[c]
            i_m = im_row[c]

            # Exposición efectiva acoplada con los 8 vecinos
            i_m_eff = calc_effective_exposure(i_m, im_neigh_row[c] / 8.0)
            i_h_eff = calc_effective_exposure(i_h, ih_neigh_row[c] / 8.0)

            # Dinámica Humana (S -> I -> R -> S con recaídas hepáticas en P. vivax)
            p_infect_h = calc_infection_probability(rate_m_to_h, i_m_eff, dt_days)
            new_infected_h = ac_sample_binomial(s_h, p_infect_h, rng)
            new_recovered_h = ac_sample_binomial(i_h, p_recover_h, rng)

            relapsed_h = ac_sample_binomial(r_h, p_relapse, rng) if params["relapse_rate"] > 0.0 else 0
            remaining_r_h = max(0, r_h - relapsed_h)
            lost_immunity_h = ac_sample_binomial(remaining_r_h, p_loss_imm_h, rng)

            sh_next_row[c] = s_h - new_infected_h + lost_immunity_h
            ih_next_row[c] = i_h + new_infected_h - new_recovered_h + relapsed_h
            rh_next_row[c] = remaining_r_h + new_recovered_h - lost_immunity_h
            cases_row[c] = new_infected_h + relapsed_h

            # Dinámica del Mosquito (Nacimiento -> S_m -> I_m -> Muerte)
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

            sm_next_row[c] = s_m_surv - new_infected_m + newborn_m
            im_next_row[c] = i_m_surv + new_infected_m

    return S_h_next, I_h_next, R_h_next, S_m_next, I_m_next, step_new_cases


# ============================================================================
# 5. INICIALIZACIÓN DE TABLEROS ESTOCÁSTICOS (ac_generate_initial_boards)
# ============================================================================


def ac_generate_initial_boards(
    *args,
    **kwargs,
) -> dict[str, Any]:
    """
    Genera los 10 tableros iniciales del modelo SIRS utilizando listas anidadas
    de Python puro y distribuciones Binomiales basadas en el IPA y la población inicial.

    Soporta tanto `ac_generate_initial_boards(df)` como `ac_generate_initial_boards(xp, df)`.
    """
    if len(args) == 1:
        df = args[0]
    elif len(args) >= 2:
        # Se pasó (xp, df)
        df = args[1]
    else:
        df = kwargs["df"]

    rng = kwargs.get("rng", None)

    df_sorted = df.sort_values("fecha")
    df_by_date = df_sorted.groupby(["fecha"], sort=True)

    first_pop = float(df_by_date["poblacion_total"].sum().iloc[0])
    board_size = max(1, math.ceil(math.sqrt(first_pop / AC_CELL_POPULATION)))

    IPA_falciparum = float(df_by_date["IPA_falciparum"].mean().iloc[0])
    IPA_vivax = float(df_by_date["IPA_vivax"].mean().iloc[0])

    p_init_falciparum = min(1.0, max(0.0, IPA_falciparum / float(AC_CELL_POPULATION)))
    p_init_vivax = min(1.0, max(0.0, IPA_vivax / float(AC_CELL_POPULATION)))

    # Humans - Falciparum (S + I + R = 1.000 por celda)
    humans_falciparum_infected_count_board = [
        [ac_sample_binomial(AC_CELL_POPULATION, p_init_falciparum, rng) for _ in range(board_size)]
        for _ in range(board_size)
    ]
    humans_falciparum_recovered_count_board = create_empty_board(board_size, 0)
    humans_falciparum_susceptible_count_board = [
        [AC_CELL_POPULATION - humans_falciparum_infected_count_board[r][c] for c in range(board_size)]
        for r in range(board_size)
    ]

    # Mosquitoes - Falciparum
    p_mosq_inf_f = min(1.0, p_init_falciparum * 2.0)
    mosquitoes_falciparum_susceptible_count_board = create_empty_board(board_size, 0)
    mosquitoes_falciparum_infected_count_board = create_empty_board(board_size, 0)
    for r in range(board_size):
        for c in range(board_size):
            init_m = ac_sample_binomial(AC_MAX_MOSQUITOES_PER_CELL, 0.25, rng)
            inf_m = ac_sample_binomial(init_m, p_mosq_inf_f, rng)
            mosquitoes_falciparum_infected_count_board[r][c] = inf_m
            mosquitoes_falciparum_susceptible_count_board[r][c] = init_m - inf_m

    # Humans - Vivax (S + I + R = 1.000 por celda)
    humans_vivax_infected_count_board = [
        [ac_sample_binomial(AC_CELL_POPULATION, p_init_vivax, rng) for _ in range(board_size)]
        for _ in range(board_size)
    ]
    humans_vivax_recovered_count_board = create_empty_board(board_size, 0)
    humans_vivax_susceptible_count_board = [
        [AC_CELL_POPULATION - humans_vivax_infected_count_board[r][c] for c in range(board_size)]
        for r in range(board_size)
    ]

    # Mosquitoes - Vivax
    p_mosq_inf_v = min(1.0, p_init_vivax * 2.0)
    mosquitoes_vivax_susceptible_count_board = create_empty_board(board_size, 0)
    mosquitoes_vivax_infected_count_board = create_empty_board(board_size, 0)
    for r in range(board_size):
        for c in range(board_size):
            init_m = ac_sample_binomial(AC_MAX_MOSQUITOES_PER_CELL, 0.25, rng)
            inf_m = ac_sample_binomial(init_m, p_mosq_inf_v, rng)
            mosquitoes_vivax_infected_count_board[r][c] = inf_m
            mosquitoes_vivax_susceptible_count_board[r][c] = init_m - inf_m

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


# ============================================================================
# 6. BUCLE MENSUAL DE SIMULACIÓN TEMPORAL (ac_apply_evolution_rules)
# ============================================================================


def ac_apply_evolution_rules(
    *args,
    **kwargs,
) -> Any:
    """
    Evoluciona los 10 tableros a lo largo de las fechas mensuales del DataFrame
    en Python puro, registrando el historial epidemiológico y las instantáneas 2D.

    Soporta tanto `ac_apply_evolution_rules(df, ac_boards_data)` como
    `ac_apply_evolution_rules(xp, df, ac_boards_data)`.
    """
    if len(args) == 2:
        df = args[0]
        ac_boards_data = args[1]
    elif len(args) >= 3:
        # Se pasó (xp, df, ac_boards_data)
        df = args[1]
        ac_boards_data = args[2]
    else:
        df = kwargs["df"]
        ac_boards_data = kwargs["ac_boards_data"]

    rng = kwargs.get("rng", None)

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
    S_hf = copy_board(ac_boards_data["humans_falciparum_susceptible_count_board"])
    I_hf = copy_board(ac_boards_data["humans_falciparum_infected_count_board"])
    R_hf = copy_board(ac_boards_data["humans_falciparum_recovered_count_board"])
    S_mf = copy_board(ac_boards_data["mosquitoes_falciparum_susceptible_count_board"])
    I_mf = copy_board(ac_boards_data["mosquitoes_falciparum_infected_count_board"])

    # Estado actual Vivax
    S_hv = copy_board(ac_boards_data["humans_vivax_susceptible_count_board"])
    I_hv = copy_board(ac_boards_data["humans_vivax_infected_count_board"])
    R_hv = copy_board(ac_boards_data["humans_vivax_recovered_count_board"])
    S_mv = copy_board(ac_boards_data["mosquitoes_vivax_susceptible_count_board"])
    I_mv = copy_board(ac_boards_data["mosquitoes_vivax_infected_count_board"])

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
                strain=MalariaType.FALCIPARUM,
                S_h=S_hf, I_h=I_hf, R_h=R_hf,
                S_m=S_mf, I_m=I_mf,
                temperature=temp, humidity=hum, monthly_precipitation=precip,
                dt_days=dt_days, rng=rng,
            )
            S_hv, I_hv, R_hv, S_mv, I_mv, new_v = ac_step_strain_day(
                strain=MalariaType.VIVAX,
                S_h=S_hv, I_h=I_hv, R_h=R_hv,
                S_m=S_mv, I_m=I_mv,
                temperature=temp, humidity=hum, monthly_precipitation=precip,
                dt_days=dt_days, rng=rng,
            )
            monthly_new_cases_f += sum_board(new_f)
            monthly_new_cases_v += sum_board(new_v)

        frames_snapshots.append({
            "fecha": pd.Timestamp(row.fecha),
            "humans_falciparum_susceptible_count_board": copy_board(S_hf),
            "humans_falciparum_infected_count_board": copy_board(I_hf),
            "humans_falciparum_recovered_count_board": copy_board(R_hf),
            "mosquitoes_falciparum_susceptible_count_board": copy_board(S_mf),
            "mosquitoes_falciparum_infected_count_board": copy_board(I_mf),
            "humans_vivax_susceptible_count_board": copy_board(S_hv),
            "humans_vivax_infected_count_board": copy_board(I_hv),
            "humans_vivax_recovered_count_board": copy_board(R_hv),
            "mosquitoes_vivax_susceptible_count_board": copy_board(S_mv),
            "mosquitoes_vivax_infected_count_board": copy_board(I_mv),
        })

        history.append({
            "fecha": row.fecha,
            "falciparum_S_h": sum_board(S_hf),
            "falciparum_I_h": sum_board(I_hf),
            "falciparum_R_h": sum_board(R_hf),
            "falciparum_S_m": sum_board(S_mf),
            "falciparum_I_m": sum_board(I_mf),
            "falciparum_nuevos_casos_mes": monthly_new_cases_f,
            "IPA_falciparum_simulado": monthly_new_cases_f / float(total_cells),
            "IPA_falciparum_real": float(row.IPA_falciparum),
            "vivax_S_h": sum_board(S_hv),
            "vivax_I_h": sum_board(I_hv),
            "vivax_R_h": sum_board(R_hv),
            "vivax_S_m": sum_board(S_mv),
            "vivax_I_m": sum_board(I_mv),
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
