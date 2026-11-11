# AGENTS.md — Guía Técnica y Referencia del Modelo SIR/SIRS en Autómatas Celulares

Este documento describe en detalle la arquitectura matemática, biológica y computacional del **Autómata Celular Estocástico 2D acoplado (SIRS Humano – SI Vectorial)** implementado en el proyecto de Computación de Alto Desempeño (HPC) para modelar la dinámica espaciotemporal de la malaria (*Plasmodium falciparum* y *Plasmodium vivax*) en Colombia (2007–2023).

Sirve como especificación formal del modelo tanto para agentes de IA como para la implementación en diferentes paradigmas y lenguajes (Python secuencial, NumPy, CuPy, C++, etc.), garantizando la consistencia epidemiológica independientemente del esquema de paralelización evaluado.

---

## 1. Visión General del Modelo

A diferencia de un modelo SIR clásico de transmisión directa (persona a persona), la malaria es una **enfermedad metaxénica (transmitida por vectores)**. Por ello, la solución implementa un **modelo metapoblacional de Ross-Macdonald sobre una cuadrícula 2D de Autómatas Celulares**, con las siguientes características clave:

1. **Metapoblación por celda (no individuos binarios):** Cada celda $(i, j)$ de la grilla representa una subpoblación local de **$N_H = 1\,000$ humanos** y una capacidad de carga máxima de **$K_M = 2\,000$ mosquitos hembra (*Anopheles*)**.
2. **Acoplamiento cruzado Humano $\leftrightarrow$ Mosquito:** Los humanos susceptibles ($S_h$) solo se infectan por picaduras de mosquitos infectados ($I_m$), y los mosquitos susceptibles ($S_m$) solo se infectan al picar humanos infectados ($I_h$).
3. **Dinámica SIRS con recaídas diferenciales por cepa:**
   - Los humanos transitan por **Susceptible ($S_h$) $\to$ Infectado ($I_h$) $\to$ Recuperado con inmunidad temporal ($R_h$) $\to$ Susceptible ($S_h$)**.
   - En ***Plasmodium vivax*** existe además la transición de **recaída hepática ($R_h \to I_h$)** producida por la reactivación de **hipnozoítos** latentes en el hígado, ausente en *Plasmodium falciparum*.
4. **Dinámica SI con ciclo vital para el vector:** Los mosquitos no se recuperan de la infección (permanecen infectantes hasta morir). Su población total por celda fluctúa dinámicamente según una tasa de emergencia modulada por el clima mensual (temperatura, humedad relativa y precipitación), dispersión desde celdas vecinas y mortalidad biológica natural (esperanza de vida media de 21 días).
5. **Enfoque regional:** El modelo evalúa las regiones naturales de Colombia (Amazonía, Andina, Caribe, Orinoquía y Pacífico) a lo largo de una serie temporal mensual (204 meses entre 2007 y 2023) proveniente del dataset consolidado [`GAM_regional_enriquecido.parquet`](data/GAM_regional_enriquecido.parquet).

---

## 2. Representación Espacial y Dimensionamiento del Tablero

### 2.1. Escala demográfica y tamaño de grilla $L \times L$
Para cada entidad geográfica (región), se toma la población total inicial $P_0$ (`poblacion_total` en la primera fecha de la serie temporal) y se dimensiona una cuadrícula cuadrada de lado $L$:

$$L = \max\left(1,\; \left\lceil \sqrt{\frac{P_0}{N_H}} \right\rceil\right), \quad \text{con } N_H = 1\,000\text{ hab./celda}$$

- **Total de celdas del tablero:** $N_{\text{celdas}} = L^2$.
- **Población humana modelada en la grilla:** $P_{\text{grilla}} = L^2 \times 1\,000$.
- **Capacidad máxima de mosquitos por celda:** $K_M = 2\,000$ ([`AC_MAX_MOSQUITOES_PER_CELL`](python/domain/constants.py#L9-L12)), lo que equivale a un ratio máximo vector-humano $m_{\max} = \frac{K_M}{N_H} = 2.0$.

### 2.2. Topología espacial y Vecindad de Moore
Cada celda $(i, j)$ interactúa con sus **8 celdas vecinas inmediatas (Vecindad de Moore $3 \times 3$)** bajo **condiciones de frontera periódicas (toroide 2D)**. En la implementación vectorizada ([`ac_count_neighbors`](python/adapters/utils_npcp.py#L97-L115)), la suma de los 8 vecinos se calcula mediante desplazamientos circulares (`roll`) en los ejes vertical, horizontal y diagonal:

$$N_{\text{Moore}}(X)_{i,j} = \sum_{(\Delta r, \Delta c) \in \{-1,0,1\}^2 \setminus \{(0,0)\}} X_{(i+\Delta r)\bmod L,\; (j+\Delta c)\bmod L}$$

El promedio vecinal utilizado en las ecuaciones de acoplamiento y dispersión es $\overline{X}_{\text{vecinos}}(i,j) = \frac{1}{8} N_{\text{Moore}}(X)_{i,j}$.

---

## 3. Estructura de Estado: Los 10 Tableros (`ACBoardType`)

Cada entidad geográfica mantiene **10 matrices 2D de enteros de 32 bits (`int32`)** de dimensión $L \times L$ (5 para *P. falciparum* y 5 para *P. vivax*), definidas en [`ACBoardType`](python/domain/enums.py#L4-L23):

| Enum (`ACBoardType`) | Llave en estructura de datos | Símbolo | Descripción | Mapa de color (`cmap`) |
| :--- | :--- | :---: | :--- | :---: |
| `HUMANS_FALCIPARUM_SUSCEPTIBLE` | `humans_falciparum_susceptible_count_board` | $S_{h,f}$ | Humanos susceptibles a *P. falciparum* por celda | `YlGnBu` |
| `HUMANS_FALCIPARUM_INFECTED` | `humans_falciparum_infected_count_board` | $I_{h,f}$ | Humanos infectados con *P. falciparum* por celda | `YlOrRd` |
| `HUMANS_FALCIPARUM_RECOVERED` | `humans_falciparum_recovered_count_board` | $R_{h,f}$ | Humanos recuperados/inmunes temporales (*P. falciparum*) | `Greens` |
| `MOSQUITOES_FALCIPARUM_SUSCEPTIBLE` | `mosquitoes_falciparum_susceptible_count_board` | $S_{m,f}$ | Mosquitos vivos susceptibles (*P. falciparum*) | `PuBu` |
| `MOSQUITOES_FALCIPARUM_INFECTED` | `mosquitoes_falciparum_infected_count_board` | $I_{m,f}$ | Mosquitos vivos infectantes (*P. falciparum*) | `OrRd` |
| `HUMANS_VIVAX_SUSCEPTIBLE` | `humans_vivax_susceptible_count_board` | $S_{h,v}$ | Humanos susceptibles a *P. vivax* por celda | `YlGnBu` |
| `HUMANS_VIVAX_INFECTED` | `humans_vivax_infected_count_board` | $I_{h,v}$ | Humanos infectados con *P. vivax* por celda | `YlOrRd` |
| `HUMANS_VIVAX_RECOVERED` | `humans_vivax_recovered_count_board` | $R_{h,v}$ | Humanos recuperados/portadores de hipnozoítos (*P. vivax*) | `Greens` |
| `MOSQUITOES_VIVAX_SUSCEPTIBLE` | `mosquitoes_vivax_susceptible_count_board` | $S_{m,v}$ | Mosquitos vivos susceptibles (*P. vivax*) | `PuBu` |
| `MOSQUITOES_VIVAX_INFECTED` | `mosquitoes_vivax_infected_count_board` | $I_{m,v}$ | Mosquitos vivos infectantes (*P. vivax*) | `OrRd` |

### Invariantes de conservación en todo paso $t$
Para cada celda $(i, j)$ y cada cepa $s \in \{\text{falciparum}, \text{vivax}\}$:
- **Conservación de población humana:**
  $$S_{h,s}(i,j,t) + I_{h,s}(i,j,t) + R_{h,s}(i,j,t) = 1\,000$$
- **Cota de capacidad vectorial:**
  $$0 \le S_{m,s}(i,j,t) + I_{m,s}(i,j,t) \le 2\,000$$

---

## 4. Inicialización Estocástica Basada en el IPA (`ac_generate_initial_boards`)

### 4.1. Justificación estadística del muestreo Binomial frente a asignación determinista
El **Índice Parasitario Anual (IPA)** reportado en los datasets (`IPA_falciparum`, `IPA_vivax`) mide el número de casos por cada $1\,000$ habitantes.
- Si se asignara determinísticamente $I_{h,s}(i,j,0) = \text{round}(\text{IPA}_s)$, en regiones o meses donde $\text{IPA}_s < 0.5$ todas las celdas recibirían exactamente $0$ infectados, extinguiendo artificialmente la transmisión desde $t = 0$. Además, un valor constante eliminaría la heterogeneidad espacial propia de los focos endémicos (*clusters*).
- Por ello, en [`ac_generate_initial_boards`](python/adapters/utils_npcp.py#L11-L94) se interpreta el IPA inicial como la esperanza matemática de una distribución Binomial sobre los $N_H = 1\,000$ habitantes de cada celda:

$$p_{0,s} = \text{clip}\left(\frac{\overline{\text{IPA}}_{s,0}}{1\,000},\; 0,\; 1\right)$$

### 4.2. Estado inicial en $t = 0$
Para cada celda $(i, j)$ y cepa $s$:
1. **Humanos:**
   $$I_{h,s}(i,j,0) \sim \text{Binomial}(n = 1\,000,\; p = p_{0,s})$$
   $$R_{h,s}(i,j,0) = 0, \qquad S_{h,s}(i,j,0) = 1\,000 - I_{h,s}(i,j,0)$$
2. **Mosquitos (población basal inicial al 25% de la capacidad de carga):**
   $$M_{\text{total},s}(i,j,0) \sim \text{Binomial}(n = 2\,000,\; p = 0.25)$$
   $$I_{m,s}(i,j,0) \sim \text{Binomial}\big(n = M_{\text{total},s}(i,j,0),\; p = \min(1.0,\; 2\,p_{0,s})\big)$$
   $$S_{m,s}(i,j,0) = M_{\text{total},s}(i,j,0) - I_{m,s}(i,j,0)$$

---

## 5. Formulación Matemática y Reglas de Evolución (`ac_step_strain_day`)

### 5.1. Discretización temporal sub-mensual (`AC_STEPS_PER_MONTH`)
Los datasets climáticos tienen resolución mensual ($D_{\text{mes}} \in \{28, 29, 30, 31\}$ días). Para capturar la dinámica intrames sin incurrir en el costo de 30 iteraciones diarias por mes, cada mes se divide en `AC_STEPS_PER_MONTH = 4` sub-pasos (aproximadamente semanales):

$$\Delta t = \frac{D_{\text{mes}}}{4} \approx 7.5\text{ días}$$

Todas las tasas diarias se escalan rigurosamente por $\Delta t$ dentro de [`ac_step_strain_day`](python/adapters/utils_npcp.py#L148-L236).

### 5.2. Modulación Climática ($f_s(T)$, $g(H)$, $h(P)$)
En cada mes se extraen la temperatura media $T$ (`temperatura_media_Celsius`), la humedad relativa mediana $H$ (`humedad_mediana_pct`) y la precipitación media mensual $P$ (`precipitacion_media_mm`):

1. **Factor térmico de esporogonia por cepa $f_s(T) \in [0, 1]$:**
   Modela la ventana térmica del desarrollo extrínseco del parásito en el vector (nula fuera del rango $[T_{\min,s}, 38^\circ\text{C}]$):
   $$f_s(T) = \begin{cases} \exp\left(-\dfrac{(T - T_{\text{opt},s})^2}{2\,\sigma_{T,s}^2}\right), & \text{si } T_{\min,s} < T < 38^\circ\text{C} \\ 0, & \text{en otro caso} \end{cases}$$
2. **Factor sigmoidal de humedad relativa $g(H) \in (0, 1)$:**
   Refleja la supervivencia del vector adulto (óptima cuando $H \ge 65\%$):
   $$g(H) = \frac{1}{1 + \exp\big(-0.15\,(H - 65.0)\big)}$$
3. **Factor de disponibilidad de criaderos por precipitación $h(P) \in [0.05, 1.0]$:**
   $$h(P) = \min\left(1.0,\; \max\left(0.05,\; \frac{P}{200.0}\right)\right)$$
4. **Índice compuesto de idoneidad climática (`climate_suitability`):**
   $$\Phi_s(T, H, P) = f_s(T) \cdot g(H) \cdot h(P)$$

### 5.3. Exposición Efectiva con Acoplamiento Vecinal
Con el parámetro de acoplamiento espacial $\alpha = 0.25$ (`AC_NEIGHBOR_COUPLING`), una celda $(i, j)$ recibe el $75\%$ de la presión infecciosa de su propia celda y el $25\%$ del promedio de sus 8 vecinos de Moore, normalizado por la población humana de la celda ($N_H = 1\,000$):

$$I_{m,\text{eff}}(i,j) = \frac{(1 - \alpha)\,I_m(i,j) + \alpha\,\overline{I_m}_{\text{vecinos}}(i,j)}{N_H}$$

$$I_{h,\text{eff}}(i,j) = \frac{(1 - \alpha)\,I_h(i,j) + \alpha\,\overline{I_h}_{\text{vecinos}}(i,j)}{N_H}$$

### 5.4. Reglas de Transición para la Población Humana ($S_h \to I_h \to R_h \to S_h$)
Sea $a = 0.30\text{ días}^{-1}$ (`AC_BITING_RATE`) la tasa diaria de picadura y $b_s$ la probabilidad de transmisión mosquito $\to$ humano:

1. **Tasa efectiva de contacto infeccioso vector $\to$ humano:**
   $$r_{m \to h, s} = \text{clip}(a \cdot b_s,\; 0,\; 1)$$
2. **Probabilidad de infección humana en el sub-paso $\Delta t$ (proceso de escape exponencial/geométrico):**
   $$p_{\text{inf}, h}(i,j) = \text{clip}\Big(1 - (1 - r_{m \to h, s})^{I_{m,\text{eff}}(i,j)\,\Delta t},\; 0,\; 1\Big)$$
3. **Probabilidad de recuperación clínica ($I_h \to R_h$):**
   $$p_{\text{rec}, h} = \min\left(1.0,\; \frac{\Delta t}{\tau_{\text{rec}, s}}\right)$$
4. **Probabilidad de recaída hepática por hipnozoítos ($R_h \to I_h$, exclusiva de *P. vivax*):**
   $$p_{\text{relapse}, h} = \min\Big(1.0,\; 1 - (1 - \rho_{\text{relapse}, s})^{\Delta t}\Big)$$
5. **Probabilidad de pérdida de inmunidad temporal ($R_h \to S_h$):**
   $$p_{\text{loss}, h} = \min\left(1.0,\; \frac{\Delta t}{\tau_{\text{imm}, s}}\right)$$
6. **Muestreo estocástico de flujos humanos y actualización:**
   $$\Delta I_h^{\text{nuevo}} \sim \text{Binomial}(S_h,\; p_{\text{inf}, h}), \qquad \Delta R_h^{\text{nuevo}} \sim \text{Binomial}(I_h,\; p_{\text{rec}, h})$$
   $$\Delta I_h^{\text{recaída}} \sim \text{Binomial}(R_h,\; p_{\text{relapse}, h}), \qquad \Delta S_h^{\text{inm}} \sim \text{Binomial}(R_h - \Delta I_h^{\text{recaída}},\; p_{\text{loss}, h})$$
   $$S_h(t + \Delta t) = S_h(t) - \Delta I_h^{\text{nuevo}} + \Delta S_h^{\text{inm}}$$
   $$I_h(t + \Delta t) = I_h(t) + \Delta I_h^{\text{nuevo}} - \Delta R_h^{\text{nuevo}} + \Delta I_h^{\text{recaída}}$$
   $$R_h(t + \Delta t) = R_h(t) - \Delta I_h^{\text{recaída}} + \Delta R_h^{\text{nuevo}} - \Delta S_h^{\text{inm}}$$

### 5.5. Reglas de Transición para la Población de Mosquitos ($\text{Nacimiento} \to S_m \to I_m \to \text{Muerte}$)
1. **Mortalidad natural ($\tau_{\text{vida}, m} = 21\text{ días}$):**
   $$p_{\text{muerte}, m} = \min\left(1.0,\; \frac{\Delta t}{21.0}\right)$$
   $$D_{S_m} \sim \text{Binomial}(S_m,\; p_{\text{muerte}, m}), \qquad D_{I_m} \sim \text{Binomial}(I_m,\; p_{\text{muerte}, m})$$
   $$S_m^{\text{surv}} = S_m - D_{S_m}, \qquad I_m^{\text{surv}} = I_m - D_{I_m}$$
2. **Emergencia climática y dispersión vecinal sobre espacios vacíos:**
   $$\text{Slots}_{\text{vacíos}}(i,j) = \max\Big(0,\; K_M - \big(S_m^{\text{surv}}(i,j) + I_m^{\text{surv}}(i,j)\big)\Big)$$
   $$p_{\text{nac}, m}(i,j) = \text{clip}\left(\left[\beta_{\text{clima}}\,\Phi_s(T,H,P) + \beta_{\text{vecinos}}\,\frac{\overline{M_{\text{vivos}}}_{\text{vecinos}}(i,j)}{K_M}\right]\Delta t,\; 0,\; 1\right)$$
   donde $\beta_{\text{clima}} = 0.12$ (`AC_MOSQUITO_WEATHER_DENSITY`) y $\beta_{\text{vecinos}} = 0.04$ (`AC_MOSQUITO_NEIGHBORS_DENSITY`). Los nuevos mosquitos emergen como susceptibles:
   $$\Delta S_m^{\text{nac}} \sim \text{Binomial}(\text{Slots}_{\text{vacíos}},\; p_{\text{nac}, m})$$
3. **Infección del vector ($S_m \to I_m$) al picar humanos infectados:**
   Modulada tanto por la infectividad humano $\to$ mosquito ($c_s$) como por la viabilidad térmica de esporogonia $f_s(T)$:
   $$r_{h \to m, s} = \text{clip}\big(a \cdot c_s \cdot f_s(T),\; 0,\; 1\big)$$
   $$p_{\text{inf}, m}(i,j) = \text{clip}\Big(1 - (1 - r_{h \to m, s})^{I_{h,\text{eff}}(i,j)\,\Delta t},\; 0,\; 1\Big)$$
   $$\Delta I_m^{\text{nuevo}} \sim \text{Binomial}(S_m^{\text{surv}},\; p_{\text{inf}, m})$$
   $$S_m(t + \Delta t) = S_m^{\text{surv}} - \Delta I_m^{\text{nuevo}} + \Delta S_m^{\text{nac}}, \qquad I_m(t + \Delta t) = I_m^{\text{surv}} + \Delta I_m^{\text{nuevo}}$$

### 5.6. Métricas Epidemiológicas Mensuales
Al finalizar los 4 sub-pasos de cada mes, [`ac_apply_evolution_rules`](python/adapters/utils_npcp.py#L238-L352) registra:
- **Nuevos casos mensuales por cepa:**
  $$\text{Casos}_{\text{mes}, s} = \sum_{k=1}^{4} \sum_{i,j} \left(\Delta I_{h,s}^{\text{nuevo}}(i,j,k) + \Delta I_{h,s}^{\text{recaída}}(i,j,k)\right)$$
- **IPA simulado mensual (casos por cada $1\,000$ habitantes):**
  $$\text{IPA}_{\text{simulado}, s} = \frac{\text{Casos}_{\text{mes}, s}}{L^2}$$
  *(Dado que cada una de las $L^2$ celdas equivale a $1\,000$ habitantes, dividir por $L^2$ entrega directamente la tasa por cada $1\,000$ habitantes, comparable con `IPA_falciparum` e `IPA_vivax` del dataset).*

---

## 6. Parámetros Biológicos Calibrados (`AC_STRAIN_PARAMS`)

Definidos en [`AC_STRAIN_PARAMS`](python/domain/constants.py#L36-L54):

| Parámetro | Clave en código | *P. falciparum* | *P. vivax* | Justificación biológica y epidemiológica |
| :--- | :--- | :---: | :---: | :--- |
| Temp. mínima esporogonia | `t_min` | $18.0\,^\circ\text{C}$ | $15.0\,^\circ\text{C}$ | *P. vivax* completa su ciclo extrínseco a temperaturas más bajas, explicando su mayor presencia en zonas templadas/andinas. |
| Temp. óptima transmisión | `t_opt` | $28.0\,^\circ\text{C}$ | $26.0\,^\circ\text{C}$ | *P. falciparum* alcanza su máxima eficiencia en climas cálidos tropicales (Pacífico, Urabá, Amazonía). |
| Amplitud térmica ($\sigma_T$) | `t_sigma` | $4.5\,^\circ\text{C}$ | $5.0\,^\circ\text{C}$ | *P. vivax* exhibe un nicho térmico ligeramente más amplio. |
| Prob. mosquito $\to$ humano ($b$) | `prob_mosquito_to_human` | $0.35$ | $0.30$ | Mayor carga parasitaria esporozoítica e infectividad aguda en *P. falciparum*. |
| Prob. humano $\to$ mosquito ($c$) | `prob_human_to_mosquito` | $0.30$ | $0.40$ | En *P. vivax* los gametocitos aparecen tempranamente (antes de los síntomas clínicos), facilitando la infección del vector. |
| Duración media infección ($\tau_{\text{rec}}$) | `recuperation_days` | $14.0\text{ días}$ | $21.0\text{ días}$ | Tratamiento más rápido/agudo en *P. falciparum* frente a infecciones más prolongadas en *P. vivax*. |
| Duración inmunidad ($\tau_{\text{imm}}$) | `immunity_loss_days` | $90.0\text{ días}$ | $120.0\text{ días}$ | Ventana de protección humoral temporal tras superar el episodio agudo antes de volver a $S_h$. |
| Tasa diaria de recaída ($\rho_{\text{relapse}}$) | `relapse_rate` | $0.0$ | $0.0015\text{ d}^{-1}$ | Solo *P. vivax* forma **hipnozoítos hepáticos** capaces de reactivar la infección meses después. |

---

## 7. Aspectos Computacionales y Muestreo Estocástico

### 7.1. Muestreador Binomial Vectorizado (`ac_fast_binomial`)
En tableros de gran escala (como la **Región Andina** con $\sim 28$ millones de habitantes $\Rightarrow L = 168 \Rightarrow 28\,224$ celdas), invocar generadores escalares de variables aleatorias binomiales celda por celda (por ejemplo el algoritmo de rechazo BTPE) genera un cuello de botella computacional severo.
La función [`ac_fast_binomial`](python/adapters/utils_npcp.py#L127-L145) implementa una aproximación asintótica continua vectorizada en `float32`:
- Si $\max(n \cdot p) \le 0$: retorna una matriz de ceros en $O(1)$.
- Si $\max(n \cdot p) < 10$: utiliza muestreo de **Poisson** $\text{Poisson}(\mu = n \cdot p)$.
- Si $\max(n \cdot p) \ge 10$: utiliza la **aproximación Normal truncada** $\text{clip}\big(\text{round}(\mu + \sigma Z),\; 0,\; n\big)$ con $\sigma = \sqrt{n\,p\,(1-p)}$ y $Z \sim \mathcal{N}(0, 1)$.

Cualquier implementación paralela o en otro lenguaje (C++, CUDA, etc.) debe mantener la equivalencia numérica de estas distribuciones o documentar la variante del generador de números pseudoaleatorios (PRNG) empleado.

### 7.2. Registro de Estado e Historial de Simulación
Para cada mes simulado se consolida el conteo total por compartimento en toda la grilla junto con las métricas epidemiológicas (nuevos casos e IPA simulado). Adicionalmente, las implementaciones pueden conservar instantáneas (*snapshots*) de los 10 tableros por mes para alimentar el módulo de visualización y animación ([`ac_animate_boards`](python/adapters/utils_animations.py#L12-L163)).

---

## 8. Estándar de Benchmark y Registro de Rendimiento (`outputs/times.csv`)

Para permitir la comparación rigurosa de desempeño, escalabilidad (*strong/weak scaling*), aceleración (*Speedup* $S_p = T_1 / T_p$) y eficiencia ($E_p = S_p / p$) entre todas las implementaciones evaluadas en la asignatura (Python puro, NumPy, CuPy, multiprocesamiento, C++ serial, OpenMP, MPI, CUDA, etc.), **todas las implementaciones deben persistir sus métricas en el archivo consolidado [`outputs/times.csv`](outputs/times.csv)** siguiendo un esquema unificado.

### 8.1. Esquema de Columnas Consolidado

| Columna | Tipo | Descripción | Ejemplo / Valores permitidos |
| :--- | :---: | :--- | :--- |
| `execution_timestamp` | `float` | Timestamp UNIX (`time.time()`) del instante en que finaliza la ejecución de la simulación. | `1794369499.072` |
| `language` | `string` | Lenguaje de programación base de la implementación. | `python`, `cpp` |
| `paradigm` | `string` | Modelo computacional, acelerador o paradigma de paralelización empleado. | `pure` (secuencial), `numpy`, `cupy`, `multiprocessing`, `openmp`, `mpi`, `cuda` |
| `region` | `string` | Región geográfica evaluada en minúsculas. | `amazonia`, `andina`, `caribe`, `orinoquia`, `pacifico` |
| `workers` | `int` | Cantidad efectiva de unidades de procesamiento (hilos o procesos) asignadas al cómputo. | `1` para serial/puro o monoproceso; $p \ge 2$ para multihilo/multiproceso; `1` para GPU mononodo. |
| `board_size` | `int` | Dimensión de lado $L$ del tablero 2D ($L \times L$ celdas). | `30`, `39`, `87`, `96`, `154` |
| `iterations` | `int` | Cantidad de pasos temporales mensuales simulados en la serie. | `204` (serie 2007–2023) |
| `elapsed_time` | `float` | Tiempo transcurrido de cómputo en segundos con alta precisión (`perf_counter()`), midiendo **estrictamente la simulación temporal** (excluyendo I/O y renderizado de gráficos/animaciones). | `2.3455` |

### 8.2. Reglas de Medición y Consistencia

1. **Aislamiento del tiempo de simulación (`elapsed_time`):**
   - El cronómetro debe iniciar inmediatamente antes del bucle de evolución temporal y detenerse justo después de completar las 204 iteraciones mensuales.
   - **No debe incluir:** lectura de archivos Parquet/CSV en disco, preprocesamiento inicial del dataset, ni generación/renderizado HTML de las animaciones interactivas.
2. **Definición de `workers` para cálculo de Speedup:**
   - En implementaciones secuenciales puras (`pure` o `serial`) y vectorizadas monohilo, debe registrarse explícitamente `workers = 1`.
   - Registrar la cantidad total de cores de la máquina (`os.cpu_count()`) en ejecuciones monohilo falsea el cálculo de Speedup ($S_p = T_1 / T_p$).
   - En ejecuciones paralelas (`multiprocessing`, `openmp`, `mpi`), `workers` debe corresponder exactamente al número de hilos o procesos de trabajo activos ($p$).
3. **Modo de escritura (Append / Concurrencia):**
   - Toda ejecución debe abrir [`outputs/times.csv`](outputs/times.csv) en modo anexado (`append` / `"a"`). Si el archivo no existe, debe crearse escribiendo primero la fila de encabezados completa:
     ```csv
     execution_timestamp,language,paradigm,region,workers,board_size,iterations,elapsed_time
     ```
4. **Dimensiones de tablero por región ($L$):**
   - Para garantizar la comparabilidad entre diferentes lenguajes y modelos paralelos, todas las implementaciones deben calcular $L = \lceil\sqrt{P_0 / 1\,000}\rceil$ a partir de la población inicial de cada región, arrojando:
     - **Amazonía:** $L = 30$ ($900$ celdas)
     - **Orinoquía:** $L = 39$ ($1\,521$ celdas)
     - **Pacífico:** $L = 87$ ($7\,569$ celdas)
     - **Caribe:** $L = 96$ ($9\,216$ celdas)
     - **Andina:** $L = 154$ ($23\,716$ celdas)

---

## 9. Estándar de Validación Epidemiológica y Exportación de Métricas (`outputs/metrics/{paradigm}_{region}.csv`)

Dado que las implementaciones en diferentes paradigmas (Python puro, NumPy, CuPy, multiprocesamiento, C++, OpenMP, MPI, CUDA) emplean diferentes generadores de números pseudoaleatorios (PRNG) y aproximaciones de muestreo, **la validación de corrección computacional entre paradigmas es de naturaleza estadística** (según la Sección 5.7 de la guía del proyecto).

Para habilitar este análisis, **toda implementación debe persistir la serie temporal mensual de la simulación en un archivo CSV individual en `outputs/metrics/{paradigm}_{region}.csv`**.

### 9.1. Esquema de Columnas del Archivo de Métricas

El archivo CSV consta de 18 columnas registradas a lo largo de las 204 fechas mensuales evaluadas (ordenadas cronológicamente de 2007-01 a 2023-12):

| Columna | Tipo | Descripción |
| :--- | :---: | :--- |
| `paradigm` | `string` | Paradigma o modelo de paralelización (`pure`, `numpy`, `cupy`, `openmp`, `mpi`, `cuda`, etc.). |
| `region` | `string` | Región geográfica evaluada en minúsculas (`amazonia`, `andina`, `caribe`, `orinoquia`, `pacifico`). |
| `fecha` | `string` | Fecha mensual correspondiente a la serie (`YYYY-MM-DD`). |
| `falciparum_S_h` | `int` | Suma de humanos susceptibles ($S_h$) en toda la cuadrícula para *P. falciparum*. |
| `falciparum_I_h` | `int` | Suma de humanos infectados ($I_h$) en toda la cuadrícula para *P. falciparum*. |
| `falciparum_R_h` | `int` | Suma de humanos recuperados/inmunes ($R_h$) en toda la cuadrícula para *P. falciparum*. |
| `falciparum_S_m` | `int` | Suma de mosquitos susceptibles ($S_m$) en toda la cuadrícula para *P. falciparum*. |
| `falciparum_I_m` | `int` | Suma de mosquitos infectantes ($I_m$) en toda la cuadrícula para *P. falciparum*. |
| `falciparum_nuevos_casos_mes` | `int` | Nuevos casos humanos acumulados en los 4 sub-pasos del mes ($\sum \Delta I_{h,f}^{\text{nuevo}}$). |
| `IPA_falciparum_simulado` | `float` | Incidencia mensual simulada por cada 1.000 habitantes (`falciparum_nuevos_casos_mes` / $L^2$). |
| `IPA_falciparum_real` | `float` | Incidencia mensual real observada reportada en el dataset INS. |
| `vivax_S_h` | `int` | Suma de humanos susceptibles ($S_h$) en toda la cuadrícula para *P. vivax*. |
| `vivax_I_h` | `int` | Suma de humanos infectados ($I_h$) en toda la cuadrícula para *P. vivax*. |
| `vivax_R_h` | `int` | Suma de humanos recuperados/portadores latentes ($R_h$) en toda la cuadrícula para *P. vivax*. |
| `vivax_S_m` | `int` | Suma de mosquitos susceptibles ($S_m$) en toda la cuadrícula para *P. vivax*. |
| `vivax_I_m` | `int` | Suma de mosquitos infectantes ($I_m$) en toda la cuadrícula para *P. vivax*. |
| `vivax_nuevos_casos_mes` | `int` | Nuevos casos acumulados en el mes ($\sum \Delta I_{h,v}^{\text{nuevo}} + \sum \Delta I_{h,v}^{\text{recaída}}$). |
| `IPA_vivax_simulado` | `float` | Incidencia mensual simulada por cada 1.000 habitantes (`vivax_nuevos_casos_mes` / $L^2$). |
| `IPA_vivax_real` | `float` | Incidencia mensual real observada reportada en el dataset INS. |

### 9.2. Criterios de Aceptación para Validación Estadística

Para certificar que una implementación paralela o en otro lenguaje es equivalente al modelo de referencia, se deben evaluar los siguientes tres criterios sobre estos CSV:

1. **Invariante de Conservación Demográfica:**
   En cada fila mensual $t$, debe cumplirse estrictamente la conservación de la población humana total en la grilla:
   $$(S_{h,f} + I_{h,f} + R_{h,f}) = L^2 \times 1\,000$$
   $$(S_{h,v} + I_{h,v} + R_{h,v}) = L^2 \times 1\,000$$
   Es decir, a nivel de columnas del CSV:
   - `falciparum_S_h + falciparum_I_h + falciparum_R_h == L^2 * 1000`
   - `vivax_S_h + vivax_I_h + vivax_R_h == L^2 * 1000`
2. **Superposición de Curvas Medias en Bandas de Confianza (Sección 5.7):**
   Al promediar $N$ réplicas independientes de una implementación, la trayectoria de su curva media mensual de `IPA_simulado` debe situarse dentro de las bandas de confianza (o $\mu \pm 2\sigma$) obtenidas por el paradigma de referencia.
3. **Coincidencia del Tamaño Final Medio dentro del Error Estándar:**
   El tamaño epidémico acumulado final $C_{\text{final}} = \sum_{t=1}^{204} \text{Casos}_{\text{mes}}(t)$ (sumando la columna `nuevos_casos_mes` de cada cepa) promedio entre réplicas debe coincidir entre implementaciones dentro del error estándar combinado:
   $$|\bar{C}_A - \bar{C}_B| \le 2 \cdot \sqrt{\text{SE}_A^2 + \text{SE}_B^2}, \quad \text{con } \text{SE} = \frac{\sigma}{\sqrt{N}}$$

### 9.3. Reglas de Medición y Persistencia
- **Exclusión del tiempo de simulación:** La escritura de los archivos en `outputs/metrics/` debe realizarse **después** de detener el cronómetro de `elapsed_time` reportado en `outputs/times.csv`.
- **Réplicas Monte Carlo:** En experimentos con múltiples réplicas estocásticas, los archivos deben nombrarse como `outputs/metrics/{paradigm}_{region}_run{id}.csv` o incluir la columna `run_id`.

---

## 10. Consideraciones y Limitaciones Metodológicas (Para Discusión del Informe)

Al redactar la sección de **Discusión de Resultados y Limitaciones del Modelo**, se deben considerar los siguientes puntos técnicos sobre el comportamiento de la simulación:

1. **Ausencia de control vectorial y tratamiento farmacológico en el modelo mecanicista:**
   El modelo SIRS simula la **transmisión natural libre** gobernada exclusivamente por el clima y la inmunidad temporal. En consecuencia, una vez que la idoneidad climática $\Phi_s(T, H, P)$ supera el umbral epidémico ($R_0 > 1$), el modelo converge hacia un equilibrio endémico alto ($\text{IPA}_{\text{simulado}} \sim 150 - 400$), mientras que el $\text{IPA}_{\text{real}}$ reportado por el INS se mantiene varios órdenes de magnitud por debajo gracias al diagnóstico temprano, tratamiento con cloroquina/primaquina o derivados de artemisinina, uso de toldillos y fumigación.
2. **Diferencia dinámica entre *P. vivax* y *P. falciparum*:**
   En las curvas simuladas se observa que *P. vivax* despega más rápido y sostiene una prevalencia endémica superior, incluso en meses menos cálidos. Esto es consecuencia directa de tres mecanismos implementados: su menor umbral térmico ($15^\circ\text{C}$ vs $18^\circ\text{C}$), su mayor infectividad humano $\to$ mosquito ($c = 0.40$ vs $0.30$) y el reservorio hepático de recaídas ($\rho_{\text{relapse}} = 0.0015\text{ d}^{-1}$).
3. **Clima homogéneo por entidad y condiciones de borde toroidales:**
   Cada región recibe en cada paso mensual el promedio espacial de temperatura, humedad y precipitación de su jurisdicción, por lo que la heterogeneidad espacial dentro de un mismo tablero emerge del proceso estocástico Binomial y de la difusión local en la vecindad de Moore, no de gradientes topográficos internos a la celda.
4. **Independencia de tableros entre cepas:**
   Las dinámicas de *P. falciparum* y *P. vivax* evolucionan en tableros paralelos sobre la misma población de $1\,000$ humanos por celda, lo que equivale a asumir posibilidad de coinfección/superinfección sin inmunidad cruzada completa entre ambas especies.
