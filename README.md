# Proyecto final de Computación de Alto Desempeño

## Integrantes

- Daniel Solarte ([@dsolartec](https://github.com/dsolartec))
- Samuel Marroquin ([@SamuelMarroquin2009-12](https://github.com/SamuelMarroquin2009-12))
- Juan Esteban Ramirez ([@juanes779](https://github.com/juanes779))

## Contexto del problema

La malaria (paludismo) es una afección parasitaria transmitida por mosquitos hembra del género Anopheles que exhibe una acentuada heterogeneidad espaciotemporal en Colombia. La transmisión se concentra en focos endémicos y epidémicos específicos (como la Costa Pacífica, Urabá-Bajo Cauca-Alto San Jorge, Amazonía y Orinoquía), regulada por gradientes climáticos, regímenes hidrológicos y dinámicas de movilidad poblacional.

El modelo utilizado para la simulación del contagio entre mosquitos y humanos para cada cepa de malaria (P. Vivax y P. Falciparum) es el Ross-Macdonald, este describe el comportamiento de esa interacción en un rango de días en base al clima de la región analizada (Se adaptó a que fuera mensual).

Se están analizando dos cepas diferentes porque una de ellas vive en temperaturas altas (P. Vivax) y otra en temperaturas bajas (P. Falciparum) dando como resultado que una cepa predomina sobre la otra en cada región del país, pero la que predomina a nivel general es la P. Vivax.

Los datos utilizados para la simulación corresponden a los entregados por la Guía de Atención Médica (GAM) del Ministerio de Salud de Colombia desde Enero de 2007 hasta Diciembre de 2023.

## Python

### Pre-requisitos

- Python >=3.14 - [Guía de Instalación](https://wiki.python.org/python/getting-started/BeginnersGuide/Download.html)
- Poetry >=2.4.1 - [Documentación](https://python-poetry.org/docs/)

```bash
pipx install poetry==2.4.1
```
> Comando para instalar Poetry usando PIP

### Ejecución

Toda la ejecución del programa para Python está en el [README.md](./python/README.md) de la carpeta de Python, los comandos debes ejecutarlos dentro de esa carpeta, para dirigirte a ella puedes usar `cd python` en tu terminal.

## C++

Implementaciones compiladas del mismo autómata celular: secuencial, OpenMP (memoria compartida) y MPI (memoria distribuida). Son un port directo de la versión de Python puro (`python/adapters/utils_pure.py`) siguiendo la especificación de [AGENTS.md](./AGENTS.md).

### Pre-requisitos

- g++ >= 9 con soporte de C++17 y OpenMP
- OpenMPI (`mpicxx`, `mpirun`)
- make
- Python con pandas (solo para exportar el dataset a CSV y validar resultados)

```bash
sudo apt install build-essential openmpi-bin libopenmpi-dev
```
> Comando para instalar el compilador y OpenMPI en Ubuntu / WSL

```bash
brew install gcc open-mpi
```
> Comando para instalar el compilador y OpenMPI en macOS. El `g++` de Apple es clang y no incluye OpenMP, por eso el `Makefile` usa automáticamente el `g++-NN` de Homebrew (puedes forzarlo con `make CXX=g++-14`)

### Preparación de los datos

Los programas en C++ no leen Parquet: leen `data/GAM_regional_enriquecido.csv`, que se genera **una sola vez** desde la raíz del repositorio:

```bash
python tools/export_csv.py
```

### Compilación

> **NOTA:** TODOS los comandos de compilación y ejecución de C++ deben ejecutarse dentro de la carpeta `cpp/`, para dirigirte a ella puedes usar `cd cpp` en tu terminal.

```bash
make
```

| Objetivo | Descripción |
|---|---|
| `make` / `make all` | Compila las tres versiones |
| `make secuencial` | Compila solo la versión secuencial |
| `make openmp` | Compila solo la versión OpenMP |
| `make mpi` | Compila solo la versión MPI |
| `make clean` | Elimina los ejecutables |

Banderas usadas: `-O3 -march=native -std=c++17 -Wall -Wextra -Wpedantic` (más `-fopenmp` en OpenMP; en ARM/macOS `-mcpu=native` en lugar de `-march=native`). Compila sin advertencias. `make info` muestra el compilador y las banderas que se usarán.

### Ejecución

```bash
./secuencial --region amazonia
```
> Versión secuencial (`paradigm="serial"`, `workers=1`)

```bash
./openmp --region pacifico --threads 4
```
> Versión OpenMP (`paradigm="openmp"`, `workers=4`). También se puede usar `OMP_NUM_THREADS=4 ./openmp --region pacifico`

```bash
mpirun -np 4 ./mpi --region pacifico
```
> Versión MPI (`paradigm="mpi"`, `workers=4`). No uses más procesos que núcleos físicos tenga tu máquina

### Argumentos opcionales

| Argumento | Descripción | Valores aceptados | Valor por defecto |
|---|---|---|---|
| `--region` | Región a utilizar en el modelo | `amazonia`, `andina`, `caribe`, `orinoquia`, `pacifico` o `todo` | pacifico |
| `--runs` | Cantidad de réplicas (repeticiones) a ejecutar y registrar | Entero >= 1 | 1 |
| `--seed` | Semilla base del generador de números aleatorios | Entero >= 0 | 12345 |
| `--no-metrics` | No escribir los CSV de métricas | N/A | N/A |
| `--warmup` | Ejecuciones de calentamiento que no se registran | Entero >= 0 | 1 |
| `--threads` | (Solo OpenMP) Cantidad de hilos; tiene prioridad sobre `OMP_NUM_THREADS` | Entero >= 1 | `OMP_NUM_THREADS` |
| `--schedule` | (Solo OpenMP) Tipo de planificación del bucle paralelo | `static`, `dynamic`, `guided` | static |
| `--data` | Ruta del CSV de entrada | Ruta | `../data/GAM_regional_enriquecido.csv` |
| `--outdir` | Carpeta de resultados | Ruta | `../outputs` |
| `--board-size` | Solo para el experimento de escalabilidad débil: fuerza el lado del tablero | Entero >= 1 | El de la región |

> **Modo de uso:** `mpirun -np 4 ./mpi --region amazonia --runs 5 --seed 12345`

### Resultados generados

Cada ejecución genera:
- Una fila por réplica en `../outputs/times.csv` con `language="cpp"`, `paradigm` igual a `serial`, `openmp` o `mpi`, y `workers` igual a 1, la cantidad de hilos o la cantidad de procesos respectivamente. El tiempo mide únicamente el bucle de las 204 iteraciones mensuales (en MPI es el tiempo del proceso más lento).
- El historial y métricas mensuales en `../outputs/metrics/{paradigm}_{region}.csv`, o `../outputs/metrics/{paradigm}_{region}_run{id}.csv` cuando `--runs` es mayor que 1. Se escriben después de detener el cronómetro.

### Generador de números aleatorios y reproducibilidad

- Generador `std::mt19937_64` y muestreo `std::binomial_distribution` (Binomial exacta, igual que Python puro).
- Cada **fila** del tablero tiene su propio flujo aleatorio, sembrado con un hash de (semilla, réplica, mes, sub-paso, cepa, fila). Por eso las tres versiones producen **exactamente el mismo CSV de métricas** para la misma semilla, sin importar la cantidad de hilos o procesos:

```bash
./secuencial --region amazonia --warmup 0 && mpirun -np 4 ./mpi --region amazonia --warmup 0
cmp <(cut -d, -f2- ../outputs/metrics/serial_amazonia.csv) <(cut -d, -f2- ../outputs/metrics/mpi_amazonia.csv) && echo "Idénticos"
```
> Comprobación de que la paralelización no altera el resultado (se ignora la primera columna, que es el nombre del paradigma)

### Benchmark y validación

Estos comandos se ejecutan desde la raíz del repositorio:

```bash
bash tools/benchmark_cpp.sh amazonia pacifico
```
> Ejecuta serial, OpenMP (1, 2, 4 y 8 hilos) y MPI (1, 2 y 4 procesos) con 5 réplicas cada uno. Variables opcionales: `RUNS`, `SEED`, `THREADS`, `PROCS`

```bash
python tools/validate_metrics.py
```
> Revisa en cada CSV de métricas: 204 filas, columnas, conservación de la población humana y cota de mosquitos

```bash
python tools/pure_replicas.py --region amazonia --runs 8
```
> Genera réplicas con semilla de la referencia en Python puro (`pure_{region}_run{id}.csv`)

```bash
python tools/compare_stats.py
```
> Compara cada paradigma contra Python puro (tamaño epidémico final e IPA medio dentro de 2 errores estándar, [AGENTS.md](./AGENTS.md) sección 9.2) y escribe `outputs/validation_summary.csv`

```bash
bash tools/hardware_info.sh > outputs/hardware.txt
```
> Registra el hardware y las versiones con las que se midió

### CUDA

TODO (Daniel): Hacer la guía del kernel de CUDA

## Ejecución completa con un solo comando

Con el entorno de Python activado y las herramientas instaladas, este comando ejecuta todo el experimento de CPU: datos, compilación, benchmarks, validación, notebook, informe y presentación. Detecta los núcleos físicos del equipo y no lanza más hilos o procesos que esos.

```bash
RAPIDO=1 bash tools/run_all.sh
```
> Prueba rápida (pocos minutos): solo Amazonía y 2 repeticiones

```bash
bash tools/run_all.sh
```
> Medición completa con 5 repeticiones por configuración. Borra `outputs/times.csv` y las métricas anteriores para no mezclar equipos (usa `LIMPIAR=0` para evitarlo)

## Análisis de resultados

El notebook [`notebooks/analisis.ipynb`](./notebooks/analisis.ipynb) genera **todas** las figuras y tablas del informe en `outputs/figures/` a partir de `outputs/times.csv`, `outputs/metrics/` y `outputs/experiments/`. Si faltan resultados de algún paradigma (por ejemplo CuPy o CUDA), la figura se genera sin él y se muestra un aviso.

```bash
pip install jupyter matplotlib python-pptx
```
> Comando para instalar las dependencias del notebook y de la presentación

El informe en PDF necesita además `pandoc` y Google Chrome o Chromium (`brew install pandoc` o `sudo apt install pandoc chromium`).

```bash
jupyter execute --inplace notebooks/analisis.ipynb
```
> Ejecuta el notebook completo desde la raíz del repositorio (también puedes usar *Run All* en Jupyter o VS Code)

```bash
python tools/build_informe.py
```
> Genera `informe.pdf` a partir de `docs/informe_plantilla.md`, rellenando las cifras con las tablas del notebook

```bash
python tools/build_presentacion.py
```
> Genera `docs/presentacion.pptx` y el guion `docs/presentacion.md` con las mismas cifras

## Documentación

| Archivo | Contenido |
|---|---|
| [`AGENTS.md`](./AGENTS.md) | Especificación del modelo y de los formatos de salida |
| [`informe.pdf`](./informe.pdf) | Informe científico (generado desde [`docs/informe_plantilla.md`](./docs/informe_plantilla.md)) |
| [`ENTREGA_PARA_DANIEL.md`](./ENTREGA_PARA_DANIEL.md) | Qué se entregó, justificación de cada decisión y cómo ejecutarlo en macOS |
| [`docs/presentacion.md`](./docs/presentacion.md) y `docs/presentacion.pptx` | Guion y diapositivas de la sustentación |
| [`docs/ACUERDOS_GUIA_VS_REPO.md`](./docs/ACUERDOS_GUIA_VS_REPO.md) | Correspondencia entre la guía del curso y la estructura de este repositorio |
| [`docs/CHECKLIST_REVISION.md`](./docs/CHECKLIST_REVISION.md) | Comandos para reproducir todo y origen de cada número del informe |

## Formato de los resultados (Carpeta `outputs`)

### Archivo de tiempos de ejecución (`times.csv`)

En este archivo se consolidarán todas las ejecuciones que se realicen utilizando el proyecto (tanto en Python como en C++ y sus variantes paralelas), siguiendo este esquema:

| Columna | Descripción |
|---|---|
| execution_timestamp | Timestamp UNIX del momento en que finaliza la simulación |
| language | Lenguaje de programación empleado (`python`, `cpp`) |
| paradigm | Paradigma computacional (`pure`, `numpy`, `cupy`, `multiprocessing`, `serial`, `openmp`, `mpi`, etc.) |
| region | Región geográfica evaluada (`amazonia`, `andina`, `caribe`, `orinoquia`, `pacifico`) |
| workers | Cantidad efectiva de hilos o procesos de cómputo utilizados (1 para secuencial monoproceso) |
| board_size | Tamaño del lado del tablero ($L$), es decir, si el valor es 30, el tablero es de 30x30 celdas |
| iterations | Cantidad de iteraciones mensuales simuladas del modelo SIRS (204 meses) |
| elapsed_time | Tiempo transcurrido de simulación en segundos (excluyendo I/O y renderizado) |

### Animaciones

Se guardará cada animación resultante en formato HTML para poder visualizarla con botones interactivos, esta se hará en base a los resultados de cada ejecución.

> **NOTA:** Solo se guardará una animación por librería y región.
