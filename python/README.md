# Proyecto final de Computación de Alto Desempeño (Python)

> **NOTA:** TODOS los comandos descritos en este archivo deben ejecutarse dentro de la carpeta `python/`, asegúrate que estés dentro de la carpeta antes de empezar.

## Instalación de dependencias

Para instalar las dependencias del proyecto asegúrate de ejecutar el siguiente comando en tu terminal:

```bash
poetry install
```

## Ejecución secuencial

Para ejecutar el modelo SIR que usa código puro en Python (Secuencial), utiliza el siguiente comando:

```bash
poetry run python main.py pure
```

### Argumentos opcionales

| Argumento | Descripción | Valores aceptados | Valor por defecto |
|---|---|---|---|
| `region` | Región a utilizar en el model | `Amazonia`, `Andina`, `Caribe`, `Orinoquia`, `Pacifico` o `todo` | Pacifico |
| `disable-animation` | Desactivar la generación de la animación HTML | N/A | N/A |

> **Modo de uso:** `poetry run main.py pure --disable-animation`

### Resultados generados

Este comando genera:
- Las gráficas animadas de cada uno de los 10 tableros SIR de cada región evaluada en `../outputs/animations/pure_{region}.html`.
- El historial y métricas mensuales de la simulación en `../outputs/metrics/pure_{region}.csv` para análisis y validación estadística.
- El registro de rendimiento en el archivo `../outputs/times.csv` con `language="python"`, `paradigm="pure"`, `workers=1` y la región evaluada.

## Ejecución paralelo CPU

Para la paralelización en CPU se eligió `multiprocessing` (librería estándar de Python), con **dos estrategias** que se pueden comparar:

| Estrategia | Qué se reparte | Implementación | `paradigm` en `times.csv` |
|---|---|---|---|
| `replicas` (por defecto) | R simulaciones completas e independientes (ensamble Monte Carlo) entre p procesos | `adapters/utils_parallel.py` | `multiprocessing` |
| `franjas` | Una sola simulación, repartida por franjas de filas entre p procesos con memoria compartida y barreras | `adapters/utils_mp.py` | `multiprocessing_franjas` |

La estrategia por defecto es la de réplicas porque la guía del curso indica que ese es el "nivel natural" para multiprocessing (cada tarea corre una simulación completa). La de franjas se conserva para comparar ambos esquemas, igual que la guía pide hacerlo con MPI.

Utiliza el siguiente comando:

```bash
poetry run python main.py multiprocessing
```

### Argumentos opcionales

| Argumento | Descripción | Valores aceptados | Valor por defecto |
|---|---|---|---|
| `region` | Región a utilizar en el model | `Amazonia`, `Andina`, `Caribe`, `Orinoquia`, `Pacifico` o `todo` | Pacifico |
| `estrategia` | Estrategia de paralelización | `replicas`, `franjas` | replicas |
| `workers` | Cantidad de procesos de trabajo (p) | Entero >= 1 | 4 |
| `runs` | Réplicas: tamaño del lote R. Franjas: cantidad de simulaciones (una fila de `times.csv` por cada una) | Entero >= 1 | 8 en replicas, 1 en franjas |
| `seed` | Semilla base (réplicas: la réplica k usa `seed + k`; franjas: el proceso k usa `seed + 1000·run + k`) | Entero >= 0 | 12345 |
| `kernel` | (Solo réplicas) Implementación que ejecuta cada réplica | `numpy`, `pure` | numpy |
| `disable-animation` | Desactivar la generación de la animación HTML | N/A | N/A |

> **Modo de uso:** `poetry run python main.py multiprocessing --region amazonia --workers 4 --runs 8 --disable-animation`

> **Modo de uso (franjas):** `poetry run python main.py multiprocessing --estrategia franjas --region amazonia --workers 4 --runs 5 --disable-animation`

### Resultados generados

Este comando genera:
- La gráfica animada de la réplica 0 de cada región evaluada en `../outputs/animations/multiprocessing_{region}.html`.
- El historial y métricas mensuales de cada réplica en `../outputs/metrics/multiprocessing_{region}_run{id}.csv` para análisis y validación estadística.
- El registro de rendimiento en el archivo `../outputs/times.csv` con `language="python"`, `paradigm="multiprocessing"` (o `multiprocessing_franjas`), `workers` igual a la cantidad exacta de procesos y la región evaluada.
- Con `--estrategia franjas`, las métricas van a `../outputs/metrics/multiprocessing_franjas_{region}[_run{id}].csv` y el arranque de los procesos se informa aparte (no se incluye en `elapsed_time`).

### Definición del speedup

> **IMPORTANTE:** En este paradigma `elapsed_time` es el tiempo total de las R réplicas con p procesos (no el de una sola simulación).

Para que el speedup sea honesto, la línea base es **el mismo R ejecutado con 1 proceso** (`--workers 1`):

$$S_p = \frac{T(R, 1)}{T(R, p)}, \qquad E_p = \frac{S_p}{p}$$

No se compara contra una sola ejecución de `pure` o `numpy`, porque eso mezclaría el tamaño del trabajo con el efecto de la paralelización. Para comparar con los demás paradigmas se usa el tiempo por réplica (`elapsed_time / R`).

### Réplicas frente a franjas

- **Réplicas:** la validación del proyecto es estadística y necesita varias réplicas, así que el ensamble es trabajo que se debe hacer de todos modos y no requiere ninguna comunicación entre procesos. Es la estrategia más eficiente.
- **Franjas:** acelera *una* simulación. Los tableros viven en memoria compartida (`multiprocessing.shared_memory`) con doble búfer, y los procesos se sincronizan con una barrera por sub-paso y dos por mes; nunca se copian tableros por tuberías. Paga esa sincronización y el registro mensual en el proceso principal, por lo que su eficiencia es menor, pero es la estrategia que haría falta con tableros mucho más grandes. Es el mismo esquema que se implementó en C++ con MPI.

### Benchmark

```bash
bash ../tools/benchmark_python_mp.sh amazonia pacifico
```
> Ejecuta 1, 2, 4 y 8 procesos con 5 repeticiones cada uno. Variables opcionales: `REPS`, `WORKERS`, `RUNS` y `ESTRATEGIA=franjas` para medir la segunda estrategia

## Ejecución con NumPy

Para ejecutar el modelo SIR que usa la librería de NumPy, utiliza el siguiente comando:

```bash
poetry run python main.py numpy
```

### Argumentos opcionales

| Argumento | Descripción | Valores aceptados | Valor por defecto |
|---|---|---|---|
| `region` | Región a utilizar en el model | `Amazonia`, `Andina`, `Caribe`, `Orinoquia`, `Pacifico` o `todo` | Pacifico |
| `disable-animation` | Desactivar la generación de la animación HTML | N/A | N/A |

> **Modo de uso:** `poetry run main.py numpy --region andina`

### Resultados generados

Este comando genera:
- Las gráficas animadas de cada uno de los 10 tableros SIR de cada región evaluada en `../outputs/animations/numpy_{region}.html`.
- El historial y métricas mensuales de la simulación en `../outputs/metrics/numpy_{region}.csv` para análisis y validación estadística.
- El registro de rendimiento en el archivo `../outputs/times.csv` con `language="python"`, `paradigm="numpy"`, `workers=1` y la región evaluada.

## Ejecución con CuPy

TODO (Daniel): Hacer guía para CuPy
