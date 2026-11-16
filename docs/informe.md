<!-- Generado por tools/build_informe.py a partir de docs/informe_plantilla.md. No editar a mano. -->

# Paralelización de un autómata celular estocástico para la dinámica de la malaria en Colombia

**Daniel Solarte · Samuel Marroquin · Juan Esteban Ramírez** — Computación de Alto Desempeño (HPC) 2026-2 · Universidad de Medellín

## Resumen

La malaria es una enfermedad transmitida por vectores cuya incidencia en Colombia varía
fuertemente entre regiones y a lo largo del tiempo. En este trabajo se toma un modelo ya
construido —un autómata celular estocástico bidimensional que acopla una dinámica SIRS en
humanos con una dinámica SI en mosquitos, en la tradición de Ross-Macdonald, para
*Plasmodium falciparum* y *P. vivax*— y se estudia cómo reducir su tiempo de ejecución con
los paradigmas de cómputo vistos en el curso. El mismo problema, con los mismos parámetros
y 204 meses de datos climáticos (2007–2023) para cinco regiones, se implementó en Python
puro, NumPy, Python con `multiprocessing`, CuPy, C++ secuencial, C++ con OpenMP y C++ con
MPI. [TODO (Daniel): resultados de CuPy y del kernel CUDA.] La corrección se validó en dos niveles: las tres
versiones en C++ producen resultados idénticos bit a bit para cualquier número de hilos o
procesos gracias a un flujo aleatorio por fila del tablero, y la equivalencia entre
lenguajes se evaluó estadísticamente con réplicas Monte Carlo. En un equipo de 4 núcleos se obtuvo
un speedup máximo de 3,67 respecto a C++ secuencial (MPI con p = 4 en Andina) y de
3,86 respecto a NumPy (multiprocessing con p = 4 en Pacífico). La fracción paralela ajustada con la
ley de Amdahl fue 0,915 para OpenMP, 0,955 para MPI y 0,995 para el ensamble con
`multiprocessing`. Tres hallazgos no previstos resultaron de las mediciones: una
contención entre hilos causada por el estado global de la función `lgamma` de la biblioteca
de C, que limitaba la escalabilidad de OpenMP; un sesgo relativo del orden de 10⁻⁴ en el
generador binomial de la biblioteca estándar de C++; y una desviación grande del muestreo
aproximado de NumPy cuando una especie está cerca del umbral epidémico. Los dos últimos
fueron detectados por la validación estadística. Se discute qué paradigma conviene según el tamaño del tablero y el tipo de
estudio (una simulación grande o un ensamble de réplicas).

**Palabras clave:** malaria, autómatas celulares, Ross-Macdonald, OpenMP, MPI,
multiprocessing, GPU, escalabilidad, Monte Carlo.

---

## 1. Introducción

La malaria es causada por parásitos del género *Plasmodium* y se transmite por la picadura
de mosquitos hembra del género *Anopheles*. Sigue siendo una de las enfermedades
infecciosas de mayor carga en el mundo (World Health Organization, 2023). En Colombia la
transmisión se concentra en focos como la costa Pacífica, la Amazonía y la Orinoquía, y
depende de la temperatura, la humedad y la lluvia, que condicionan tanto la supervivencia
del mosquito como el desarrollo del parásito dentro de él (Mordecai et al., 2013).

Los modelos matemáticos permiten explorar cómo cambia la transmisión cuando cambia el
clima. Un modelo espacial y estocástico es más realista que uno de ecuaciones diferenciales
promediadas, pero tiene dos costos: cada paso de tiempo recorre todas las celdas de una
malla, y, por ser estocástico, una sola ejecución no basta: hay que repetir la simulación
muchas veces para estimar medias e incertidumbres. Ambos costos son precisamente los que la
computación de alto desempeño puede reducir.

El modelo epidemiológico usado aquí fue desarrollado previamente por uno de los autores en
otro curso; **no es el objeto de estudio de este trabajo**. El objetivo es llevar ese único
problema por todos los paradigmas del curso y explicar, con mediciones propias, por qué
cada versión se comporta como lo hace. Las preguntas que guían el trabajo son:

1. ¿Cuánto se acelera la simulación con cada paradigma y respecto a qué referencia?
2. ¿Qué fracción del programa es paralelizable y qué limita la escalabilidad?
3. ¿Cuándo conviene cada paradigma (memoria compartida, memoria distribuida, ensamble de
   procesos, GPU) según el tamaño del problema?
4. ¿Cómo garantizar que versiones con generadores aleatorios distintos resuelven el mismo
   problema?

El documento se organiza así: la sección 2 presenta el marco teórico; la 3, el modelo y sus
parámetros; la 4, las implementaciones y sus decisiones de paralelización; la 5, la
metodología de medición; las secciones 6 y 7, los resultados del problema y de rendimiento;
la 8, el análisis y las limitaciones; y la 9, las conclusiones.

---

## 2. Marco teórico

### 2.1 Modelos compartimentales y el modelo de Ross-Macdonald

Los modelos compartimentales dividen la población en estados —susceptible (S), infectado
(I), recuperado (R)— y describen los flujos entre ellos (Kermack y McKendrick, 1927). En un
modelo SIRS la inmunidad es temporal y los recuperados vuelven a ser susceptibles.

La malaria no se transmite de persona a persona: requiere al vector. Ross (1911) formuló el
primer modelo que acopla la población humana con la de mosquitos, y Macdonald (1957) lo
amplió incorporando la supervivencia del mosquito y el período de incubación del parásito.
La familia de modelos resultante se conoce como Ross-Macdonald (Smith et al., 2012). Sus
ingredientes son: la tasa de picadura *a*, la probabilidad de transmisión de mosquito a
humano *b*, la de humano a mosquito *c*, la razón mosquitos/humanos *m* y la mortalidad del
mosquito. Los humanos susceptibles solo se infectan por mosquitos infectantes, y los
mosquitos susceptibles solo se infectan al picar humanos infectados; el mosquito no se
recupera (dinámica SI).

*P. vivax* se distingue de *P. falciparum* en que forma hipnozoítos, estadios latentes en
el hígado que reactivan la infección semanas o meses después (White, 2011). En el modelo
esto aparece como una transición adicional de recuperado a infectado, exclusiva de *P.
vivax*.

### 2.2 Autómatas celulares

Un autómata celular es un sistema dinámico discreto en espacio y tiempo: una malla de
celdas cuyo estado se actualiza simultáneamente según una regla local que depende de la
propia celda y de su vecindad. Se han usado ampliamente para modelar la propagación
espacial de epidemias (White, del Rey y Sánchez, 2007). En este trabajo cada celda no es un
individuo sino una **subpoblación** (metapoblación) de 1 000 humanos y hasta 2 000
mosquitos; la vecindad es la de Moore (las 8 celdas adyacentes) y las fronteras son
periódicas (toroide). La regla es estocástica: los flujos entre compartimentos se sortean
con distribuciones binomiales.

Desde el punto de vista computacional, la actualización de un autómata celular es un
**stencil**: el nuevo valor de una celda depende de un vecindario fijo de la iteración
anterior. Este patrón tiene dos propiedades relevantes para la paralelización: (i) con
doble buffer —se lee de la malla "actual" y se escribe en la "siguiente"— todas las celdas
de un paso son independientes entre sí; y (ii) si la malla se reparte entre procesos, cada
uno solo necesita de los demás una franja delgada de borde (filas fantasma).

### 2.3 Métricas y leyes de escalabilidad

Sea *T₁* el tiempo de referencia y *Tₚ* el tiempo con *p* unidades de procesamiento. El
**speedup** es *S = T₁ / Tₚ* y la **eficiencia** *E = S / p*. La ley de Amdahl (1967)
establece que, si una fracción *f* del programa es paralelizable, el speedup con tamaño
fijo está acotado por

*S(p) = 1 / [(1 − f) + f / p]*.

Gustafson (1988) observó que en la práctica el tamaño del problema crece con los recursos;
el speedup escalado es entonces *S(p) = (1 − f) + f·p*. La primera ley corresponde a la
**escalabilidad fuerte** (tamaño fijo) y la segunda a la **escalabilidad débil** (tamaño
proporcional a *p*). La fracción serial determinada experimentalmente de Karp y Flatt
(1990), *e = (1/S − 1/p) / (1 − 1/p)*, permite diagnosticar la causa de la pérdida de
eficiencia: si *e* es constante, domina la parte serial; si crece con *p*, dominan los
sobrecostos de paralelización (comunicación, sincronización, contención).

### 2.4 Números aleatorios en paralelo

En una simulación estocástica paralela, cada hilo o proceso necesita un flujo de números
aleatorios independiente. Compartir un generador produce condiciones de carrera o un cuello
de botella; repetir semillas produce réplicas idénticas y una varianza falsamente pequeña.
Las soluciones habituales son los generadores basados en contador, como Philox (Salmon et
al., 2011), o derivar semillas independientes con una función de mezcla como SplitMix
(Steele, Lea y Flood, 2014). El generador base de este trabajo en C++ es el Mersenne
Twister de 64 bits (Matsumoto y Nishimura, 1998).

---

## 3. Modelo y parámetros

La especificación completa está en `AGENTS.md`; aquí se resume lo necesario.

**Datos.** Serie mensual de enero de 2007 a diciembre de 2023 (204 meses) para cinco
regiones naturales de Colombia, con temperatura media, humedad relativa mediana,
precipitación media, población e Índice Parasitario Anual (IPA) por especie
[REFERENCIA POR VERIFICAR: fuente oficial del dataset `GAM_regional_enriquecido`; el
README cita al Ministerio de Salud y `AGENTS.md` al INS].

**Malla.** Para cada región, el lado del tablero es *L = ⌈√(P₀ / 1 000)⌉*, con *P₀* la
población inicial (Tabla 1). Cada región mantiene 10 tableros de enteros de 32 bits (5 por
especie: *S_h, I_h, R_h, S_m, I_m*).

**Tabla 1.** Tamaño del problema por región.

| Región | L | Celdas (L²) | Actualizaciones de celda por simulación (L² × 204 × 4 × 2) |
|---|---:|---:|---:|
| Amazonía | 30 | 900 | 1 468 800 |
| Orinoquía | 39 | 1 521 | 2 482 272 |
| Pacífico | 87 | 7 569 | 12 352 608 |
| Caribe | 96 | 9 216 | 15 040 512 |
| Andina | 154 | 23 716 | 38 704 512 |

**Dinámica.** Cada mes se divide en 4 sub-pasos de duración Δt = días del mes / 4. En cada
sub-paso y para cada especie:

1. Se calcula la idoneidad climática Φ = f(T)·g(H)·h(P): una campana térmica alrededor de la
   temperatura óptima de la especie, una sigmoide de humedad y una rampa de precipitación.
2. Cada celda recibe el 75 % de la presión de infección de sí misma y el 25 % del promedio
   de sus 8 vecinas.
3. Humanos: infección *S→I* (probabilidad de escape exponencial que depende de los mosquitos
   infectantes), recuperación *I→R*, recaída *R→I* (solo *P. vivax*) y pérdida de inmunidad
   *R→S*. Cada flujo es una muestra binomial.
4. Mosquitos: muerte natural, emergencia de nuevos susceptibles en los "espacios vacíos"
   hasta la capacidad de carga (modulada por el clima y por las vecinas) e infección *S→I*
   al picar humanos infectados.

Son ocho muestreos binomiales por celda, especie y sub-paso. El estado inicial se sortea a
partir del IPA del primer mes.

**Tabla 2.** Parámetros del modelo (`python/domain/constants.py`).

| Parámetro | Símbolo | *P. falciparum* | *P. vivax* |
|---|---|---:|---:|
| Humanos por celda | N_H | 1 000 | 1 000 |
| Capacidad de mosquitos por celda | K_M | 2 000 | 2 000 |
| Tasa diaria de picadura | a | 0,30 | 0,30 |
| Acoplamiento con vecinas | α | 0,25 | 0,25 |
| Vida media del mosquito (días) | 1/μ | 21 | 21 |
| Emergencia por clima / por vecinas | β | 0,12 / 0,04 | 0,12 / 0,04 |
| Temperatura mínima / óptima / amplitud (°C) | T_min, T_opt, σ | 18 / 28 / 4,5 | 15 / 26 / 5,0 |
| Prob. mosquito → humano | b | 0,35 | 0,30 |
| Prob. humano → mosquito | c | 0,30 | 0,40 |
| Duración de la infección (días) | τ_rec | 14 | 21 |
| Duración de la inmunidad (días) | τ_imm | 90 | 120 |
| Tasa diaria de recaída | ρ | 0 | 0,0015 |

**Invariantes.** En toda celda y todo paso, *S_h + I_h + R_h = 1 000* por especie, y
*0 ≤ S_m + I_m ≤ 2 000*. Estos invariantes se usan como prueba automática de corrección.

---

## 4. Implementaciones y decisiones de paralelización

Todas las versiones resuelven el mismo problema con los mismos parámetros, leen los mismos
datos y escriben los mismos formatos de salida (`outputs/times.csv` y
`outputs/metrics/{paradigma}_{región}.csv`). La Tabla 3 las resume.

**Tabla 3.** Implementaciones.

| # | Implementación | Herramienta | Unidad de paralelismo | Muestreo binomial |
|---|---|---|---|---|
| 1 | Python puro | bucles explícitos | — (referencia de corrección) | exacto (`random.binomialvariate`) |
| 2 | NumPy | operaciones vectorizadas | — (un núcleo) | aproximado: Poisson si *np* < 10, Normal truncada si no |
| 3 | Python paralelo en CPU | `multiprocessing.Pool` | réplica Monte Carlo | el de la versión que ejecuta cada réplica |
| 4 | CuPy | GPU, migración de NumPy | celda (hilos de GPU) | aproximado, igual que NumPy |
| 5 | C++ secuencial | g++ -O3 | — (línea base compilada) | exacto (`std::binomial_distribution`) |
| 6 | C++ OpenMP | memoria compartida | fila del tablero (hilo) | exacto |
| 7 | C++ MPI | memoria distribuida | franja de filas (proceso) | exacto |
| 8 | CUDA | TODO (Daniel) | TODO (Daniel) | TODO (Daniel) |

### 4.1 Python puro y NumPy

La versión pura recorre las celdas con bucles anidados sobre listas; es lenta, pero es la
traducción más literal de la especificación y por eso sirve de referencia. La versión NumPy
sustituye los bucles por operaciones sobre arreglos completos: la suma de vecinos se
obtiene con ocho desplazamientos circulares (`roll`) y los muestreos binomiales con una
aproximación vectorizada en `float32` (Harris et al., 2020). Esta aproximación es una
decisión de rendimiento que cambia ligeramente la distribución muestreada y obliga a que la
comparación entre versiones sea estadística.

### 4.2 Python paralelo en CPU: `multiprocessing`

Se implementaron **dos estrategias**, seleccionables con `--estrategia`, para comparar los
dos patrones de paralelismo del problema dentro del mismo lenguaje.

**Réplicas (estrategia por defecto).** *R* réplicas independientes (por defecto 8) se
reparten entre *p* procesos de un `Pool`, cada una con semilla `semilla + k`. Es el "nivel
natural" que la guía del curso indica para `multiprocessing`: cada tarea corre una simulación
completa y devuelve sus curvas. Además, la validación estadística exige varias réplicas, así
que el ensamble es trabajo necesario y no requiere comunicación entre procesos. El reparto es
dinámico (`imap_unordered` con `chunksize = 1`). **Definición de speedup:** la referencia
*T₁* es el mismo lote de *R* réplicas con un proceso; no se compara contra una sola
simulación, porque eso confundiría el tamaño del trabajo con el efecto del paralelismo.

**Franjas de filas (descomposición de dominio).** Una sola simulación se reparte por
franjas de filas contiguas entre *p* procesos persistentes. Los diez tableros de ambas
especies viven en memoria compartida (`multiprocessing.shared_memory`) con doble buffer, de
modo que ningún tablero viaja por tuberías: cada proceso lee de la malla actual —incluida
la fila vecina de cada borde, con frontera periódica— y escribe solo sus filas de la
siguiente. La sincronización se hace con barreras: una por sub-paso (nadie lee el estado
nuevo hasta que todos lo han escrito) y dos por mes, para que el proceso principal registre
las métricas. Cada proceso usa su propio generador (`semilla + rango`). El arranque de los
procesos se mide aparte y no entra en el tiempo de cómputo. Su referencia *T₁* es la misma
simulación con un proceso. Esta estrategia usa el núcleo de Python puro (muestreo exacto),
por lo que sus resultados se validan directamente contra la referencia.

La comparación entre ambas responde a una pregunta práctica: En Amazonía, con p = 4, la estrategia de franjas alcanzó un speedup de 2,90 (eficiencia 0,73, f de Amdahl 0,876), frente a 3,77 (eficiencia 0,94) del ensamble de réplicas. Las
réplicas no se comunican en absoluto, mientras que las franjas pagan 816 barreras por
simulación y una parte secuencial en el proceso principal (el registro mensual de
métricas), de modo que su eficiencia es necesariamente menor; a cambio, las franjas
aceleran **una** simulación, que es lo que se necesitaría con tableros mucho más grandes.

### 4.3 CuPy

TODO (Daniel): descripción de la migración NumPy → CuPy, tipo de dato, medición separada de
la copia a la GPU, el cómputo y la copia de vuelta, y sincronización antes de detener el
reloj.

### 4.4 C++ secuencial

Port directo de la versión de Python puro (`cpp/common.hpp`, `cpp/secuencial.cpp`),
compilado con `g++ -O3 -march=native -std=c++17`. Los tableros son vectores contiguos de
`int32` con dos filas fantasma; la periodicidad en columnas se resuelve con índices
precalculados. Es la línea base justa para OpenMP, MPI y GPU.

### 4.5 C++ con OpenMP (memoria compartida)

- **Qué se paraleliza:** el bucle sobre las filas del tablero en cada sub-paso
  (`#pragma omp parallel for`); en cada fila se actualizan las dos especies.
- **Condiciones de carrera:** se evitan con doble buffer. Cada hilo lee solo de la malla
  actual y escribe solo en sus propias filas de la malla siguiente; no hay bloqueos ni
  secciones críticas.
- **Acumulados:** los casos nuevos y los totales mensuales se obtienen con `reduction(+)`.
- **Scheduling:** se eligió `static` *a priori*: todas las filas tienen el mismo número de
  celdas, de modo que el reparto en bloques contiguos no tiene costo de planificación y
  conserva la localidad de caché. La elección se contrastó con una medición de las tres
  políticas (sección 7.8): `dynamic` fue un 16 % más rápido que `static` en Pacífico, lo que indica que la carga por fila **no** es uniforme: el costo del muestreo binomial depende del estado epidémico de cada celda y, en un equipo compartido, de la disponibilidad de cada núcleo.
- **Hilos:** `OMP_NUM_THREADS` o `--threads`.

### 4.6 C++ con MPI (memoria distribuida)

- **Reparto:** descomposición de dominio en una dimensión. El tablero se divide en *P*
  franjas de filas contiguas; si *L* no es divisible por *P*, los primeros *L mod P*
  procesos reciben una fila más (desbalance máximo de una fila).
- **Comunicación:** antes de cada sub-paso, cada proceso intercambia con sus dos vecinos
  las filas de borde mediante `MPI_Sendrecv` (punto a punto, sin riesgo de interbloqueo).
  La topología es un anillo: el proceso 0 es vecino del último. Se envía solo lo que la
  vecindad de Moore necesita —humanos infectados, mosquitos infectados y mosquitos
  susceptibles de ambas especies—: 6 filas de *L* enteros por dirección, en un solo mensaje.
- **Colectivas:** los totales mensuales se combinan con `MPI_Reduce` (suma) en el proceso
  0, que es el único que escribe archivos.
- **Por qué franjas y no bloques 2D:** con *L* ≤ 154 y *P* ≤ 8, las franjas tienen solo dos
  vecinos y mensajes contiguos en memoria; los bloques 2D reducirían el perímetro
  comunicado, pero con cuatro u ocho vecinos por proceso y empaquetado de columnas, una
  complejidad que no se justifica a esta escala.
- **Tiempo:** `MPI_Barrier` antes y después del bucle; se reporta el máximo entre procesos.

### 4.7 CUDA

TODO (Daniel): kernel, estrategia de números aleatorios en GPU y medición.

### 4.8 Generador de números aleatorios en C++

Se usa `std::mt19937_64` con `std::binomial_distribution`. En lugar de un generador por
hilo o proceso, **cada fila del tablero tiene su propio flujo**, cuya semilla es una mezcla
SplitMix64 de (semilla base, réplica, mes, sub-paso, especie, fila global). Consecuencias:

1. Los flujos son independientes entre hilos y procesos, porque dos filas nunca comparten
   flujo.
2. El resultado **no depende** del número de hilos, del número de procesos ni del
   scheduling: las tres versiones en C++ producen el mismo archivo de métricas para una
   misma semilla. La corrección de la paralelización se verifica entonces de forma exacta,
   no estadística.
3. Réplicas distintas usan flujos distintos.

El costo es volver a inicializar un generador por fila y sub-paso, despreciable frente a
los muestreos binomiales de la fila.

---

## 5. Metodología de medición

**Qué se mide.** Únicamente el bucle de los 204 meses. Quedan fuera la lectura de datos, la
inicialización de los tableros, la escritura de resultados y las animaciones. En C++ se usa
`std::chrono::steady_clock`; en Python, `time.perf_counter`.

**Protocolo.** Una ejecución de calentamiento no registrada, seguida de al menos 5
repeticiones por configuración; se reportan la mediana y la desviación estándar. En MPI se
sincroniza con `MPI_Barrier` y se toma el tiempo del proceso más lento. [TODO (Daniel): en
GPU se sincroniza antes de detener el reloj y las transferencias se miden por separado.]

**Registro.** Cada ejecución añade una fila a `outputs/times.csv` (marca de tiempo,
lenguaje, paradigma, región, workers, lado del tablero, iteraciones, tiempo). El notebook
deriva `outputs/tiempos.csv` con las columnas pedidas en la guía del curso.

**Semillas.** Fijas y documentadas: semilla base 12345 en C++ y `multiprocessing`; 2026
para las réplicas de referencia de Python puro.

**Hardware y software.** Todas las mediciones de CPU de este informe se hicieron el
2026-11-16 en un único equipo: Intel(R) Xeon(R) Processor @ 2.10GHz, 4 núcleos físicos, 15Gi de RAM; Ubuntu 24.04.5 LTS / kernel 6.18.44-fc-v470; g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0; mpirun (Open MPI) 4.1.6; Python 3.13.18; 2.5.3 / pandas: 3.0.5. Banderas de compilación:
`-O3 -march=native` (`-mcpu=native` en ARM) `-std=c++17`, más `-fopenmp` en OpenMP.
Todos los núcleos del equipo son equivalentes (procesador homogéneo). [TODO (Daniel): modelo de GPU, memoria, versiones de CUDA y CuPy; las
mediciones de GPU se hacen en otro equipo y así debe indicarse en cada figura.] No se usaron
más hilos o procesos que núcleos físicos; cuando una configuración los excede, se marca
como sobresuscrita y se excluye de los ajustes.

**Precisión.** El estado es entero (`int32`) en todas las versiones. Las probabilidades se
calculan en `float64` en Python puro y C++, y en `float32` en NumPy y CuPy.

**Validación.** Tres niveles:

1. *Invariantes* (`tools/validate_metrics.py`): 204 filas, columnas esperadas, conservación
   de la población humana por especie y cota de mosquitos, en todos los archivos.
2. *Exacta entre versiones de C++*: comparación byte a byte de las métricas de `serial`,
   `openmp` y `mpi` con la misma semilla.
3. *Estadística entre lenguajes* (`tools/compare_stats.py`): con *N* réplicas por
   implementación, (a) la curva media de IPA simulado debe caer dentro de la banda μ ± 2σ
   de la referencia y (b) el tamaño epidémico final medio debe coincidir dentro de dos
   errores estándar combinados, |C̄_A − C̄_B| ≤ 2·√(SE_A² + SE_B²).

---

## 6. Resultados del problema y validación

### 6.1 Resultado epidemiológico

La Figura 1 muestra, para la región Pacífico (L = 87), la evolución de los
compartimentos humanos y el IPA simulado frente al real. Tras un transitorio inicial, las
especies con clima favorable alcanzan un equilibrio endémico modulado por la estacionalidad
del clima.

![**Figura 1 (G1).** Resultado del modelo en Pacífico: compartimentos humanos (arriba) e IPA simulado frente al real en escala logarítmica (abajo). Media y banda de ±2σ entre réplicas.](../outputs/figures/G1_resultado_pacifico.png)

Dos rasgos merecen comentario. Primero, el IPA simulado queda órdenes de magnitud por
encima del real: el modelo representa transmisión libre, sin diagnóstico, tratamiento ni
control vectorial (sección 8.3). Segundo, el comportamiento depende de la región y la
especie. Donde el clima deja a una especie cerca del umbral epidémico, la epidemia crece
despacio y las réplicas divergen mucho: para *P. falciparum* en Pacífico el coeficiente de variación del
tamaño final entre réplicas es del 67 %, frente al 0,03 % de *P.
vivax* en la misma región (Figura 2). Extinción completa de la transmisión (cero casos en
los últimos 12 meses) se observó en: *P. falciparum* en Andina (probabilidad 1,00). Esto confirma que una sola
realización no caracteriza al modelo y justifica el uso de ensambles.

![**Figura 2 (P3).** Trayectorias individuales de cada réplica (líneas finas) y su media (línea gruesa) para el caso más cercano al umbral epidémico, por implementación.](../outputs/figures/P3_variabilidad_replicas.png)

### 6.2 Validación

**Invariantes.** Los 115 archivos de métricas generados se revisaron con
`tools/validate_metrics.py`; 115 cumplen todos los invariantes (204 meses,
columnas, conservación de la población humana y cota de mosquitos).

**Equivalencia exacta en C++.** Las métricas de `serial`, `openmp` y `mpi` son idénticas
para la misma semilla en las cinco regiones, con todos los números de hilos y procesos
medidos (comprobación automática en la sección G2 del notebook).

**Equivalencia estadística con Python puro.** La Tabla 4 y la Figura 3 resumen la
comparación de cada implementación contra las réplicas de Python puro.

**Tabla 4.** Validación estadística frente a Python puro. "Dentro de 2 SE" es el criterio
del tamaño epidémico final; la última columna es el porcentaje de meses en que la curva
media de IPA cae dentro de la banda μ ± 2σ de la referencia.

| Región | Especie | Implementación | Réplicas (impl. / ref.) | Diferencia del tamaño final (%) | ¿Dentro de 2 SE? | Meses dentro de la banda (%) |
|---|---|---|---:|---:|:---:|---:|
| Amazonía | *P. falciparum* | multiprocessing (núcleo NumPy) | 8 / 24 | +0,29 | no | 96 |
| Amazonía | *P. falciparum* | multiprocessing (franjas) | 3 / 24 | +0,02 | sí | 100 |
| Amazonía | *P. falciparum* | C++ secuencial | 5 / 24 | -0,18 | no | 100 |
| Amazonía | *P. vivax* | multiprocessing (núcleo NumPy) | 8 / 24 | +0,09 | no | 97 |
| Amazonía | *P. vivax* | multiprocessing (franjas) | 3 / 24 | +0,02 | sí | 100 |
| Amazonía | *P. vivax* | C++ secuencial | 5 / 24 | +0,02 | sí | 100 |
| Pacífico | *P. falciparum* | multiprocessing (núcleo NumPy) | 8 / 8 | +582 | no | 0 |
| Pacífico | *P. falciparum* | C++ secuencial | 5 / 8 | +7,32 | sí | 100 |
| Pacífico | *P. vivax* | multiprocessing (núcleo NumPy) | 8 / 8 | +0,15 | no | 92 |
| Pacífico | *P. vivax* | C++ secuencial | 5 / 8 | +0,02 | sí | 99 |

![**Figura 3 (G2).** Validación en Amazonía: curvas medias de IPA sobre la banda de la referencia (arriba) y diferencia del tamaño final con barras de ±2 errores estándar (abajo).](../outputs/figures/G2_validacion_amazonia.png)

Las curvas medias de C++ caen dentro de la banda de la referencia en al menos el
99 % de los meses y su diferencia máxima en el tamaño final es del
7,32 %; el criterio de dos errores estándar se cumple en 3 de 4 casos.
Los casos que no lo cumplen no son errores de implementación, sino dos efectos reales del
muestreo que la validación fue capaz de detectar:

**Hallazgo 1: el muestreo aproximado de NumPy cambia el resultado cerca del umbral
epidémico.** Las réplicas ejecutadas con el núcleo NumPy coinciden razonablemente con
Python puro donde la transmisión está bien establecida (diferencias de entre 0,09 % y 0,29 % en
el tamaño final), pero no en el caso cercano al umbral: *P. falciparum* en Pacífico: +582 % en el tamaño final y 0 % de los meses dentro de la banda (Figura 2). La
explicación propuesta es que `ac_fast_binomial` decide entre Poisson y Normal según el
**máximo** de *n·p* en todo el tablero; cuando alguna celda tiene *n·p* ≥ 10, todas las
celdas —incluidas las de conteos muy bajos— usan la aproximación normal redondeada, que
sobrestima la probabilidad de obtener al menos un caso cuando la media es menor que uno y
acelera artificialmente el crecimiento inicial. [TODO (Daniel): confirmar la causa y
decidir si se corrige el muestreador (elegir la aproximación celda por celda) o se documenta
como limitación; afecta también a CuPy.]

**Hallazgo 2: sesgo del generador binomial de la biblioteca estándar de C++.** Al aumentar
el número de réplicas (40 de C++ y 24 de Python puro en Amazonía), la diferencia en el
tamaño final de *P. vivax* no desapareció, sino que se estabilizó en torno al 0,03 %, por
encima de la tolerancia de dos errores estándar. La causa se aisló con una prueba
independiente (`tools/binomial_bias_test.cpp`): con 4 × 10⁷ muestras, la media de
`std::binomial_distribution` (libstdc++, g++ 13) para *n* = 1 000 y *p* = 0,03 excede a la
teórica en un factor relativo de 3,8 × 10⁻⁴ (13 errores estándar), mientras que para
*np* = 5 y *np* = 360 no se detecta sesgo. El sesgo es del mismo orden que la discrepancia
observada y es epidemiológicamente irrelevante, pero muestra que el criterio de validación
tiene potencia para detectar diferencias de centésimas de punto porcentual, y que "usar la
biblioteca estándar" no garantiza exactitud. [REFERENCIA POR VERIFICAR: algoritmo de
rechazo que implementa libstdc++ para la binomial y si el sesgo está reportado.]

---

## 7. Resultados de rendimiento

Todas las cifras provienen de `notebooks/analisis.ipynb` y corresponden a la mediana de las
repeticiones. Equipo de medición: Intel(R) Xeon(R) Processor @ 2.10GHz (4 núcleos, 15Gi RAM).

### 7.1 Tiempos por implementación y región

**Tabla 5.** Tiempo por simulación de 204 meses (segundos, mediana). Para los paradigmas
paralelos se muestra la mejor configuración sin sobresuscripción (*p* entre paréntesis);
en `multiprocessing` es el tiempo por réplica del lote.

| Región (L) | Python puro | NumPy | multiprocessing | multiprocessing (franjas) | C++ secuencial | OpenMP | MPI |
|---|---:|---:|---:|---:|---:|---:|---:|
| Amazonía (30) | 14,93 | 1,08 | 0,29 (p=4) | 4,36 (p=4) | 2,79 | 0,82 (p=4) | 0,82 (p=4) |
| Orinoquía (39) | 26,57 | 1,22 | — | — | 4,44 | 1,43 (p=4) | 1,46 (p=4) |
| Pacífico (87) | — | 3,57 | 0,93 (p=4) | — | 17,38 | 5,49 (p=4) | 4,92 (p=4) |
| Caribe (96) | — | 3,95 | — | — | 25,76 | 7,52 (p=4) | 7,75 (p=4) |
| Andina (154) | — | 6,89 | — | — | 45,59 | 13,16 (p=4) | 12,42 (p=4) |

Python puro solo se midió en Amazonía y Orinoquía (guía del curso: tamaños pequeños); es en
promedio 5,7 veces más lento que C++ secuencial y 17,8
veces más lento que NumPy.

Un resultado que puede sorprender: **NumPy en un solo núcleo es más rápido que
C++ secuencial** (3,57 s frente a 17,38 s en Pacífico, un
factor de 4,9). No es un efecto del lenguaje sino del algoritmo: NumPy
usa un muestreo binomial aproximado (una normal o una Poisson por celda, vectorizado en
`float32`), mientras que C++ usa el muestreo binomial exacto por rechazo, varias veces más
costoso por muestra. La comparación entre ambos mide, sobre todo, el precio de la exactitud
—cuyo efecto sobre el resultado se vio en la sección 6.2—.

![**Figura 4 (P1).** Tiempo por simulación de cada paradigma en cada región (escala logarítmica).](../outputs/figures/P1_paradigmas_por_region.png)

### 7.2 Tiempo frente a tamaño (G3)

El costo teórico es O(L²) por paso, es decir, pendiente 2 en escala log-log. Las pendientes
ajustadas son: NumPy: 1,18; C++ secuencial: 1,75; OpenMP: 1,72; MPI: 1,68. Las versiones compiladas quedan algo por debajo de 2 porque
en los tableros pequeños pesa un costo fijo por fila (la inicialización del generador) y
porque el costo del muestreo depende del estado epidémico de cada región, no solo del
tamaño; en NumPy domina el costo fijo de cada llamada vectorizada, que no depende de L.
Los puntos de Python puro para las regiones grandes se extrapolan con *t = c·L²* y se
dibujan huecos.

![**Figura 5 (G3).** Tiempo frente al lado del tablero, todas las implementaciones (log-log, mediana ± desviación estándar).](../outputs/figures/G3_tiempo_vs_tamano.png)

### 7.3 Speedup frente a tamaño (G4)

![**Figura 6 (G4).** Speedup por simulación respecto a NumPy (izquierda) y respecto a C++ secuencial (derecha).](../outputs/figures/G4_speedup_vs_tamano.png)

El speedup máximo respecto a C++ secuencial fue 3,67 (MPI con p = 4 en Andina), y
respecto a NumPy, 3,86 (multiprocessing con p = 4 en Pacífico). [TODO (Daniel): tamaño de cruce a
partir del cual la GPU supera a la mejor versión de CPU.]

### 7.4 Escalabilidad fuerte (G5)

**Tabla 6.** Escalabilidad fuerte en Pacífico (L = 87). Referencia: C++
secuencial para OpenMP y MPI; el mismo lote de 8 réplicas con un proceso para
`multiprocessing`.

| Paradigma | p | Tiempo (s) | Speedup | Eficiencia | Karp-Flatt e | f (Amdahl) |
|---|---:|---:|---:|---:|---:|---:|
| OpenMP | 1 | 17,65 | 0,98 | 0,98 | — | 0,915 |
| OpenMP | 2 | 9,07 | 1,92 | 0,96 | 0,043 | 0,915 |
| OpenMP | 4 | 5,49 | 3,17 | 0,79 | 0,088 | 0,915 |
| MPI | 1 | 17,09 | 1,02 | 1,02 | — | 0,955 |
| MPI | 2 | 9,36 | 1,86 | 0,93 | 0,076 | 0,955 |
| MPI | 4 | 4,92 | 3,53 | 0,88 | 0,044 | 0,955 |
| multiprocessing | 1 | 3,65 | 1,00 | 1,00 | — | 0,995 |
| multiprocessing | 2 | 1,81 | 2,01 | 1,00 | -0,005 | 0,995 |
| multiprocessing | 4 | 0,93 | 3,94 | 0,98 | 0,005 | 0,995 |

![**Figura 7 (G5).** Tiempo, speedup y eficiencia frente al número de workers en Pacífico, con la curva de Amdahl ajustada. Los puntos huecos son configuraciones sobresuscritas (más workers que núcleos).](../outputs/figures/G5_escalabilidad_fuerte_pacifico.png)

Con el máximo de workers válidos (p = 4), OpenMP alcanza un speedup de 3,17
(eficiencia 0,79), MPI 3,53 (0,88) y `multiprocessing` 3,94 (0,98).
Configuraciones sobresuscritas: OpenMP con p = 8: speedup 3,05; multiprocessing con p = 8: speedup 3,92; como era de esperar, no mejoran.
Para la estrategia de franjas de `multiprocessing` (sección 4.2): En Amazonía, con p = 4, la estrategia de franjas alcanzó un speedup de 2,90 (eficiencia 0,73, f de Amdahl 0,876), frente a 3,77 (eficiencia 0,94) del ensamble de réplicas.

### 7.5 Escalabilidad débil de MPI (G6)

Se mantuvo aproximadamente constante el número de celdas por proceso aumentando el lado
del tablero con el número de procesos (Tabla 7).

**Tabla 7.** Escalabilidad débil de MPI (clima de Pacífico).

| Procesos p | L | Celdas por proceso | Tiempo (s) | Eficiencia débil | Speedup escalado |
|---:|---:|---:|---:|---:|---:|
| 1 | 44 | 1936 | 3,73 | 1,00 | 1,00 |
| 2 | 62 | 1922 | 4,29 | 0,86 | 1,73 |
| 4 | 87 | 1892 | 4,50 | 0,81 | 3,25 |

![**Figura 8 (G6).** Escalabilidad débil de MPI: tiempo, eficiencia débil y speedup escalado frente a la predicción de Gustafson.](../outputs/figures/G6_escalabilidad_debil.png)

### 7.6 GPU (G7)

TODO (Daniel): desglose de copia a GPU, cómputo y copia de vuelta por tamaño; fracción de
transferencia.

### 7.7 Rendimiento del problema

En actualizaciones de celda por segundo (L² × 204 × 4 × 2 dividido por el tiempo), el
máximo de cada implementación fue: Python puro: 0,10 millones/s; NumPy: 5,62 millones/s; multiprocessing: 13,34 millones/s; multiprocessing (franjas): 0,34 millones/s; C++ secuencial: 0,85 millones/s; OpenMP: 2,94 millones/s; MPI: 3,12 millones/s.

![**Figura 9 (P2).** Actualizaciones de celda por segundo frente al tamaño.](../outputs/figures/P2_actualizaciones_por_segundo.png)

### 7.8 Decisiones de implementación medidas

**`lgamma` reentrante.** En las primeras mediciones, OpenMP escalaba peor que MPI en el
mismo equipo, algo inesperado para un bucle sin sincronización. La causa:
`std::binomial_distribution` llama a la función `lgamma` de la biblioteca de C al preparar
cada muestreo, y esa función escribe la variable global `signgam`. Con varios hilos, todos
escriben la misma línea de caché, que rebota entre núcleos. Los procesos de MPI no
comparten memoria y no lo sufren. Al sustituir `lgamma` por la variante reentrante
`lgamma_r`, el speedup de OpenMP mejoró sin cambio alguno en los resultados numéricos
(Tabla 8).

**Tabla 8.** Speedup de OpenMP respecto a C++ secuencial, antes y después del cambio.

| Región | Hilos | Speedup con `lgamma` (estado global) | Speedup con `lgamma_r` (reentrante) |
|---|---:|---:|---:|
| Amazonía | 4 | 2,14 | 3,40 |
| Pacífico | 4 | 2,57 | 3,17 |

![**Figura 10 (P4a).** Efecto de `lgamma` reentrante en la escalabilidad de OpenMP.](../outputs/figures/P4a_lgamma.png)

**Scheduling.** Tiempo (s, mediana) con 4 hilos según la política de
planificación (Tabla 9): `dynamic` fue un 16 % más rápido que `static` en Pacífico, lo que indica que la carga por fila **no** es uniforme: el costo del muestreo binomial depende del estado epidémico de cada celda y, en un equipo compartido, de la disponibilidad de cada núcleo.

**Tabla 9.** Tiempo de OpenMP por tipo de scheduling.

| Región | static | dynamic | guided |
|---|---:|---:|---:|
| Amazonía | 0,76 | 0,70 | 0,70 |
| Pacífico | 4,88 | 4,08 | 4,31 |

---

## 8. Análisis e interpretación

### 8.1 Respuestas a las preguntas guía

**1. Speedup máximo y referencia.** 3,67 respecto a C++ secuencial
(MPI con p = 4 en Andina) y 3,86 respecto a NumPy (multiprocessing con p = 4 en Pacífico). La conclusión
cambia con la referencia. Frente a Python puro cualquier versión parece extraordinaria,
pero esa ganancia mezcla el cambio de lenguaje con el paralelismo. Frente a NumPy, las
versiones de C++ con muestreo exacto resultan más lentas en un solo núcleo, y
la única versión de CPU que lo supera claramente es el ensamble de procesos, que ejecuta el
mismo núcleo NumPy en paralelo. La comparación justa del **paralelismo** es contra C++
secuencial; la comparación contra NumPy mide además la diferencia de algoritmo de muestreo.

**2. Fracción paralelizable.** El ajuste de Amdahl da f = 0,915 (OpenMP), 0,955
(MPI) y 0,995 (`multiprocessing`). Dentro del bucle medido, la parte estrictamente
serial es pequeña: el cálculo de las constantes del mes, la copia de dos filas fantasma por
tablero y el intercambio de punteros del doble buffer. [PENDIENTE: medir la fracción
paralela con un perfilador (`perf` o `gprof`) sobre `cpp/secuencial` y compararla.] La
fracción de Karp-Flatt indica el origen de la pérdida: en OpenMP crece de 0,043 (p = 2) a 0,088 (p = 4); en MPI
disminuye de 0,076 (p = 2) a 0,044 (p = 4); en `multiprocessing` se mantiene de -0,005 (p = 2) a 0,005 (p = 4). Cuando *e* crece con *p*, la pérdida no es
código serial sino sobrecosto de paralelización (creación de regiones paralelas en cada
sub-paso, desbalance de carga entre filas y competencia por los núcleos del equipo).

**3. ¿Cómputo o memoria?** El problema está limitado por el cómputo. Cada actualización de
celda lee del orden de 5 enteros propios más 24 de las vecinas (unos 120 bytes, en su
mayoría ya en caché porque las filas son contiguas) y ejecuta 8 muestreos binomiales, cada
uno con varias operaciones de punto flotante, logaritmos y un bucle de rechazo. La
intensidad aritmética es alta —cientos de operaciones por cada pocas decenas de bytes— y
los tableros completos caben en caché (el mayor, 10 tableros de 154 × 154 enteros, ocupa
menos de 1 MB por buffer). Por eso OpenMP no se satura por ancho de banda de memoria, y por
eso mismo el generador aleatorio domina el tiempo: optimizarlo rinde más que optimizar el
acceso a la malla. [TODO (Daniel): implicación para la GPU, donde el muestreo por rechazo
provoca divergencia entre hilos.]

**4. Cruce GPU/CPU.** TODO (Daniel).

**5. MPI: comunicación frente a cómputo.** Por sub-paso, cada proceso envía y recibe 2
mensajes de 6·*L* enteros, mientras que su cómputo es proporcional a *L²/P*. La razón
comunicación/cómputo crece como *P/L*: aumenta con el número de procesos y disminuye con el
tamaño. En escalabilidad fuerte el comportamiento sigue a Amdahl (f = 0,955). En la
débil, con p = 4 la eficiencia es 0,81 y el speedup escalado 3,25,
por debajo de la recta de Gustafson: el tiempo por proceso no se mantiene constante porque,
además de la comunicación, todos los procesos compiten por la caché compartida y la memoria
del mismo equipo. Como todos los procesos corren en un mismo equipo, los mensajes viajan
por memoria compartida, con latencias de microsegundos. En un clúster con varios nodos la
latencia de red sería uno o dos órdenes de magnitud mayor; con mensajes tan pequeños y
frecuentes (816 sub-pasos con intercambio por simulación), la comunicación pesaría más en
los tableros pequeños, y convendría agrupar el intercambio (filas fantasma más anchas para
comunicar cada varios sub-pasos) o usar tableros mayores.

**6. Precisión.** El estado es entero en todas las versiones; la precisión solo afecta al
cálculo de probabilidades. [TODO (Daniel): efecto de float32 frente a float64 en GPU.] La
diferencia de mayor impacto entre versiones no es la precisión sino el **algoritmo de
muestreo**: exacto en Python puro y C++, aproximado en NumPy y CuPy (sección 6.2).

**7. Decisión con más impacto.** La sustitución de `lgamma` por su versión reentrante: el
speedup de OpenMP con 4 hilos en Pacífico pasó de
2,57 a 3,17 (Tabla 8). En comparación, el tipo de scheduling
movió el tiempo un 16 % (Tabla 9). La lección es que el cuello de botella de un
programa paralelo puede estar en estado compartido oculto dentro de una biblioteca, no en
el código propio.

**8. Costo de desarrollo y recomendación.**

**Tabla 10.** Costo de desarrollo. Líneas de código obtenidas con `wc -l`.

| Versión | Archivos | Líneas de código | Horas |
|---|---|---:|---:|
| Python puro | `adapters/utils_pure.py` | 693 | [PENDIENTE] |
| NumPy / CuPy | `adapters/utils_npcp.py` | 352 | [PENDIENTE] |
| multiprocessing | `adapters/utils_parallel.py` | 140 (+ 90 en `main.py`) | [PENDIENTE] |
| C++ común + secuencial | `common.hpp`, `secuencial.cpp` | 570 + 67 | [PENDIENTE] |
| OpenMP (adicional) | `openmp.cpp` | 99 | [PENDIENTE] |
| MPI (adicional) | `mpi.cpp` | 155 | [PENDIENTE] |
| CUDA | TODO (Daniel) | | |

Una vez escrito el código común, OpenMP costó 99 líneas y MPI 155: la memoria compartida es
la paralelización más barata de programar, y el ensamble con `multiprocessing` (140 líneas)
la más barata de todas en relación con su eficiencia.

Recomendación para un epidemiólogo. Si el estudio consiste en **muchas réplicas de
tableros pequeños** (análisis de incertidumbre, barridos de parámetros), lo más rentable es
el ensamble: es trivial de programar, no requiere comunicación y su eficiencia fue de
0,98 con 4 procesos. Si se necesita **una simulación de un tablero grande** con
muestreo exacto, OpenMP ofrece la mejor relación entre esfuerzo y ganancia en un solo
equipo, y MPI solo se justifica cuando el tablero no cabe en un nodo o se dispone de un
clúster. Si se acepta el muestreo aproximado, NumPy es difícil de superar en CPU para estos
tamaños, pero debe validarse cerca del umbral epidémico. [TODO (Daniel): cuándo conviene la
GPU.]

### 8.2 Cuándo usar cada paradigma

| Paradigma | Conviene cuando | No conviene cuando |
|---|---|---|
| NumPy | Prototipo rápido, tableros medianos, un núcleo | Se necesita muestreo exacto o varios núcleos |
| multiprocessing | Muchas réplicas o barridos independientes | Una sola simulación; tareas muy cortas (domina el arranque de procesos) |
| OpenMP | Una simulación en un equipo multinúcleo | El problema no cabe en un nodo; hay estado compartido oculto |
| MPI | Tableros muy grandes, varios nodos | Tableros pequeños con muchos procesos (domina la comunicación) |
| GPU | TODO (Daniel) | TODO (Daniel) |

### 8.3 Limitaciones

**Del modelo** (no son objeto de este trabajo, pero condicionan la interpretación):

1. *Sin control vectorial ni tratamiento.* El modelo simula transmisión libre gobernada por
   el clima y la inmunidad temporal. Cuando la idoneidad climática supera el umbral
   epidémico, converge a un equilibrio endémico alto, mientras que el IPA real permanece
   órdenes de magnitud por debajo gracias al diagnóstico, el tratamiento y las medidas de
   control. El IPA simulado no debe leerse como predicción.
2. *Diferencia entre especies.* *P. vivax* despega antes y sostiene mayor prevalencia por
   tres mecanismos del modelo: menor umbral térmico, mayor infectividad de humano a
   mosquito y el reservorio de recaídas.
3. *Clima homogéneo por región y bordes toroidales.* Todas las celdas de una región reciben
   el mismo clima mensual; la heterogeneidad espacial surge solo del azar y de la difusión
   local. El toroide no representa la geografía real.
4. *Especies independientes.* Cada especie evoluciona en sus propios tableros sobre la misma
   población, lo que equivale a suponer coinfección sin inmunidad cruzada.

**Del estudio de rendimiento:**

5. Los tableros son pequeños (a lo sumo 23 716 celdas) frente a los tamaños en que MPI y la
   GPU muestran su ventaja; la escalabilidad débil se evaluó con un tamaño artificial.
6. MPI se midió en un solo equipo; no se evaluó el costo real de red.
7. Las mediciones de CPU y de GPU proceden de equipos distintos, por lo que su comparación
   directa debe leerse con cautela.
8. Las versiones no comparten algoritmo de muestreo (exacto frente a aproximado), de modo
   que parte de la diferencia de tiempo entre NumPy y C++ es algorítmica y no solo de
   lenguaje o paralelismo.
9. El muestreo aproximado de NumPy y CuPy altera el resultado cerca del umbral epidémico
   (sección 6.2); el generador binomial de la biblioteca estándar de C++ presenta además un sesgo
   relativo del orden de 10⁻⁴.
10. El número de núcleos físicos disponible limita el rango de *p* con mediciones válidas.

---

## 9. Conclusiones

1. Un mismo autómata celular estocástico se implementó en 7 paradigmas
   (Python puro, NumPy, multiprocessing, multiprocessing (franjas), C++ secuencial, OpenMP, MPI; pendientes: CuPy, CUDA). Las versiones de C++ dan resultados idénticos
   entre sí y sus curvas medias son estadísticamente compatibles con la referencia.
2. El speedup máximo fue 3,67 respecto a C++ secuencial (MPI con p = 4 en Andina) y
   3,86 respecto a NumPy (multiprocessing con p = 4 en Pacífico), en un equipo de 4
   núcleos. La referencia elegida cambia la lectura: la diferencia entre NumPy y C++ es,
   sobre todo, una diferencia de algoritmo de muestreo.
3. El problema está limitado por el cómputo del muestreo aleatorio, no por la memoria; por
   eso escala bien en memoria compartida una vez eliminado el estado global oculto
   (`lgamma`).
4. Diseñar los flujos aleatorios por fila, y no por hilo, convirtió la verificación del
   paralelismo en una comparación exacta y dejó la estadística solo para comparar
   lenguajes.
5. La validación estadística con suficientes réplicas detectó dos efectos reales: un sesgo
   de centésimas de punto porcentual en una biblioteca estándar y una desviación grande del
   muestreo aproximado cerca del umbral epidémico. Toda medición de tiempo debe ir
   acompañada de la evidencia de que el resultado es correcto: la versión más rápida en CPU
   fue también la menos fiel a la referencia en ese régimen.
6. Para este problema, el ensamble de réplicas es la paralelización más rentable cuando se
   estudia incertidumbre, y OpenMP lo es para una simulación individual exacta en un solo
   equipo. [TODO (Daniel): conclusión sobre GPU.]

**Trabajo futuro.** Descomposición de dominio en bloques 2D, modelo híbrido MPI + OpenMP,
un muestreador binomial exacto propio (por ejemplo, BTRS; Hörmann, 1993) compartido por
todas las versiones —incluida la vectorizada—, y tableros de resolución municipal.

---

## Referencias

Amdahl, G. M. (1967). Validity of the single processor approach to achieving large scale computing capabilities. *AFIPS Spring Joint Computer Conference Proceedings*, 30, 483–485.

Dagum, L., & Menon, R. (1998). OpenMP: An industry-standard API for shared-memory programming. *IEEE Computational Science and Engineering*, 5(1), 46–55.

Gustafson, J. L. (1988). Reevaluating Amdahl's law. *Communications of the ACM*, 31(5), 532–533.

Harris, C. R., Millman, K. J., van der Walt, S. J., et al. (2020). Array programming with NumPy. *Nature*, 585, 357–362.

Hörmann, W. (1993). The generation of binomial random variates. *Journal of Statistical Computation and Simulation*, 46(1–2), 101–110.

Kachitvichyanukul, V., & Schmeiser, B. W. (1988). Binomial random variate generation. *Communications of the ACM*, 31(2), 216–222.

Karp, A. H., & Flatt, H. P. (1990). Measuring parallel processor performance. *Communications of the ACM*, 33(5), 539–543.

Kermack, W. O., & McKendrick, A. G. (1927). A contribution to the mathematical theory of epidemics. *Proceedings of the Royal Society of London A*, 115(772), 700–721.

Macdonald, G. (1957). *The Epidemiology and Control of Malaria*. Oxford University Press.

Matsumoto, M., & Nishimura, T. (1998). Mersenne Twister: A 623-dimensionally equidistributed uniform pseudo-random number generator. *ACM Transactions on Modeling and Computer Simulation*, 8(1), 3–30.

Message Passing Interface Forum. (2021). *MPI: A Message-Passing Interface Standard, Version 4.0*.

Mordecai, E. A., Paaijmans, K. P., Johnson, L. R., et al. (2013). Optimal temperature for malaria transmission is dramatically lower than previously predicted. *Ecology Letters*, 16(1), 22–30.

Okuta, R., Unno, Y., Nishino, D., Hido, S., & Loomis, C. (2017). CuPy: A NumPy-compatible library for NVIDIA GPU calculations. *Workshop on Machine Learning Systems (LearningSys), NIPS 2017*.

Ross, R. (1911). *The Prevention of Malaria* (2.ª ed.). John Murray.

Salmon, J. K., Moraes, M. A., Dror, R. O., & Shaw, D. E. (2011). Parallel random numbers: As easy as 1, 2, 3. *Proceedings of the International Conference for High Performance Computing, Networking, Storage and Analysis (SC '11)*.

Smith, D. L., Battle, K. E., Hay, S. I., Barker, C. M., Scott, T. W., & McKenzie, F. E. (2012). Ross, Macdonald, and a theory for the dynamics and control of mosquito-transmitted pathogens. *PLoS Pathogens*, 8(4), e1002588.

Steele, G. L., Lea, D., & Flood, C. H. (2014). Fast splittable pseudorandom number generators. *Proceedings of OOPSLA '14*, 453–472.

White, N. J. (2011). Determinants of relapse periodicity in *Plasmodium vivax* malaria. *Malaria Journal*, 10, 297.

White, S. H., del Rey, A. M., & Sánchez, G. R. (2007). Modeling epidemics using cellular automata. *Applied Mathematics and Computation*, 186(1), 193–202.

World Health Organization. (2023). *World malaria report 2023*. WHO.

[REFERENCIA POR VERIFICAR] Fuente oficial de los datos de casos e IPA por región (Instituto Nacional de Salud – SIVIGILA / Ministerio de Salud y Protección Social) y de las variables climáticas del dataset `GAM_regional_enriquecido`.

[REFERENCIA POR VERIFICAR] Guía del proyecto final del curso (documento del docente, 2026-2), para citar el protocolo de medición.

> **Nota sobre las referencias:** todas las entradas sin marca corresponden a publicaciones
> reales; antes de entregar, confirmar páginas y volúmenes contra la fuente (DOI o
> editorial), en especial Amdahl (1967), Okuta et al. (2017) y Steele et al. (2014).
