from domain.enums import MalariaType


AC_CELL_POPULATION: int = 1_000
"""
Cantidad de habitantes representados por cada celda del tablero.
"""

AC_MAX_MOSQUITOES_PER_CELL: int = 2_000
"""
Capacidad de carga máxima de mosquitos vectores por celda (ratio máximo m = 2 mosquitos/humano).
"""

AC_BITING_RATE: float = 0.30
"""
Tasa diaria de picadura por mosquito (a).
"""

AC_MOSQUITO_MAX_AGE_DAYS: int = 21
"""
Esperanza de vida media del mosquito adulto en días (1 / mu_m).
"""

AC_MOSQUITO_WEATHER_DENSITY: float = 0.12
"""
Tasa de emergencia diaria de mosquitos modulada por el clima.
"""

AC_MOSQUITO_NEIGHBORS_DENSITY: float = 0.04
"""
Tasa de dispersión de mosquitos desde celdas vecinas.
"""

AC_NEIGHBOR_COUPLING: float = 0.25
"""
Fracción de exposición al contagio proveniente de las 8 celdas vecinas (vecindad de Moore).
"""

AC_STEPS_PER_MONTH: int = 4
"""
Sub-pasos de simulación por cada mes (4 = pasos semanales para acelerar la simulación vectorizada).
"""

# Parámetros específicos por cepa (Ross-Macdonald acoplado a clima)
AC_STRAIN_PARAMS: dict[MalariaType, dict[str, float]] = {
    MalariaType.FALCIPARUM: {
        "t_min": 18.0,                  # Temperatura mínima de esporogonia (°C)
        "t_opt": 28.0,                  # Temperatura óptima de transmisión (°C)
        "t_sigma": 4.5,                 # Amplitud térmica (°C)
        "prob_mosquito_to_human": 0.35, # Probabilidad de transmisión mosquito -> humano (b)
        "prob_human_to_mosquito": 0.30, # Probabilidad de transmisión humano -> mosquito (c)
        "recuperation_days": 14.0,      # Días promedio de infección humana (1 / gamma)
        "immunity_loss_days": 90.0,     # Días de inmunidad temporal antes de volver a S (1 / omega)
        "relapse_rate": 0.0,            # P. falciparum no presenta recaídas por hipnozoítos
    },
    MalariaType.VIVAX: {
        "t_min": 15.0,                  # P. vivax persiste en temperaturas más templadas (°C)
        "t_opt": 26.0,                  # Temperatura óptima de transmisión (°C)
        "t_sigma": 5.0,                 # Mayor tolerancia térmica (°C)
        "prob_mosquito_to_human": 0.30, # Probabilidad de transmisión mosquito -> humano (b)
        "prob_human_to_mosquito": 0.40, # Gametocitemia temprana facilita transmisión al vector (c)
        "recuperation_days": 21.0,      # Días promedio de infección humana (1 / gamma)
        "immunity_loss_days": 120.0,    # Días de inmunidad temporal (1 / omega)
        "relapse_rate": 0.0015,         # Tasa diaria de recaída por hipnozoítos hepáticos (R -> I)
    },
}
