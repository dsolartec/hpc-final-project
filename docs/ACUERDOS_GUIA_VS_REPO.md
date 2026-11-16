# Acuerdos: guía del profesor vs. estructura actual del repositorio

Documento para acordar en el grupo. Compara lo que pide la guía del profesor
(*Proyecto Final HPC 2026-2*, capítulos 1, 5 y 6) con lo que ya existe en el repo
(estructura de Daniel + `AGENTS.md`). Regla usada: **la guía manda en lo que se
evalúa; la estructura de Daniel se conserva en todo lo que no la contradiga.**
Cada cambio propuesto cita la sección de la guía que lo respalda.

## 1. Lo que ya coincide (no se toca)

| Requisito de la guía | Estado en el repo |
|---|---|
| §6.1/§6.3 `cpp/secuencial.cpp`, `cpp/openmp.cpp`, `cpp/mpi.cpp`, `cpp/Makefile` | Hecho con esos nombres exactos. |
| §6.3 hilos de OpenMP con `OMP_NUM_THREADS`; justificar scheduling | Hecho (`--threads` es opcional y tiene prioridad). Scheduling `static` justificado y medible con `--schedule`. |
| §6.3 MPI con comunicación explícita y reparto justificado, en un solo equipo | Hecho: franjas + `MPI_Sendrecv` + `MPI_Reduce`. |
| §6.4 medir solo el cómputo; `MPI_Barrier` y tiempo del proceso más lento | Hecho. |
| §6.4 calentamiento y ≥ 5 repeticiones, mediana y desviación | C++: `--warmup 1 --runs 5`. Python: se repite el comando 5 veces (append en `times.csv`). |
| §6.4 semillas fijas y flujos independientes | Hecho (un flujo por fila y réplica en C++; `seed + k` por réplica en multiprocessing). |
| §6.2 paralelo CPU con multiprocessing/joblib/Dask y nº de trabajadores como parámetro | Hecho: `main.py multiprocessing --workers p`. |
| §6.1 `notebooks/analisis.ipynb` genera TODAS las figuras | Pendiente (fase D), con ese nombre exacto. |
| §5.7 validación estadística (bandas de confianza, tamaño final ± error estándar) | Hecho: `tools/compare_stats.py`, coincide con `AGENTS.md` §9.2. |
| §5.7 doble buffer, fronteras iguales en todas las versiones | Hecho (toroide + vecindad de Moore, igual que `utils_pure.py`). |

## 2. Diferencias y propuesta de acuerdo

| # | La guía pide | El repo tiene (Daniel) | Propuesta | ¿Cambia la estructura? |
|---|---|---|---|---|
| D1 | §6.8: "las ejecuciones usadas en el informe deben quedar documentadas en el repositorio: los comandos exactos, las salidas completas y las mediciones en tiempos.csv". §6.9: "tiempos.csv contiene todas las mediciones". | `.gitignore` excluye `outputs/times.csv` y `outputs/metrics/{pure,numpy,cupy}_*.csv`. | **Versionar los resultados finales**: quitar esas líneas del `.gitignore` (o `git add -f`) cuando estén las mediciones definitivas. Sin esto el profesor no puede ver las mediciones. | Sí (solo `.gitignore`). |
| D2 | §6.4: `tiempos.csv` con, al menos: `implementacion, tamano, trabajadores, repeticion, t_calculo_s, t_transferencia_s, precision, equipo`. | `outputs/times.csv` con 8 columnas (`AGENTS.md` §8): faltan `repeticion`, `t_transferencia_s`, `precision`, `equipo`. | **No tocar `times.csv`** (todo el código ya escribe ese formato). El notebook deriva `outputs/tiempos.csv` con las columnas de la guía: `repeticion` = orden de la fila dentro de su configuración, `precision` y `equipo` desde `outputs/hardware.txt`. Lo único que no se puede derivar es `t_transferencia_s` → ver D3. | No (se añade un archivo derivado). |
| D3 | §6.2 y §6.4: la versión CuPy "debe medir por separado la copia de datos a la GPU, el cómputo y la copia de vuelta"; gráfica obligatoria G7 (desglose del tiempo en GPU); sincronizar antes de parar el reloj. | `handle_cupy` mide un solo `elapsed` con `perf_counter` (y sin sincronizar explícitamente). | **TODO (Daniel)**: medir los tres tiempos con `cp.cuda.Event`/`synchronize` y guardarlos, por ejemplo en `outputs/times_gpu.csv` (`execution_timestamp, paradigm, region, board_size, t_h2d, t_compute, t_d2h`). Así no se rompe el esquema de `times.csv`. | No (archivo nuevo). |
| D4 | §1.2 ítem 8 y §6.2: el kernel CUDA es opcional y puede ser `cuda/kernel.cu` (nvcc) **o** `cupy.RawKernel` desde Python (`05_cupy_rawkernel.py`). | Daniel planea "el kernel de CUDA en C++". | Sugerencia para Daniel: `cupy.RawKernel` da el mismo punto extra reutilizando la carga de datos y las métricas de Python. La regla de una celda está aislada en `step_row()` de `cpp/common.hpp` para portarla. | No. |
| D5 | §6.1: `python/01_secuencial.py`, `02_numpy.py`, `03_paralelo_cpu.py`, `04_cupy.py`, `comun.py`. | `python/main.py` con subcomandos (`pure`, `numpy`, `multiprocessing`, `cupy`) + `adapters/` + `domain/`. | **Mantener la estructura de Daniel** (es equivalente y más limpia) y documentar la correspondencia en el README (tabla abajo). Opcional, si el profesor insiste en los nombres: 4 scripts de 3 líneas que llamen a `main.py`. | No. |
| D6 | §6.1: carpeta `resultados/` (`tiempos.csv`, `validacion/`, `figuras/`). | `outputs/` (`times.csv`, `metrics/`, `animations/`). | **Mantener `outputs/`** y documentar la correspondencia. Las figuras van a `outputs/figures/`. | No. |
| D7 | §6.1/§6.7: `informe.pdf` en la raíz, 12–20 páginas. | No existía. | `informe.pdf` en la raíz, generado con `tools/build_informe.py` desde `docs/informe_plantilla.md` (las cifras salen de las tablas del notebook). | No. |
| D8 | §6.6 G6: escalabilidad débil de MPI (tamaño proporcional al nº de procesos). | Los tamaños están fijados por región (L = 30…154). | Argumento **solo experimental** `--board-size L` en los binarios C++ para G6 (no altera las corridas por región; sus tiempos van a `outputs/experiments/weak/`, no a `times.csv`). | No (argumento opcional). |
| D9 | §1.5/§6.4: cada tabla y figura indica el hardware; no lanzar más procesos/hilos que núcleos físicos. | No hay registro de hardware. | `outputs/hardware.txt` (generado con `tools/hardware_info.sh`) y nota en cada figura. La corrida de 8 hilos/procesos solo es válida en máquinas con ≥ 8 núcleos físicos. | No. |
| D10 | §1.5/§6.4: misma precisión en todas las versiones (float32 en GPU) o medir ambas. | Estado en `int32` en todas; probabilidades en `float64` (pure, C++) y `float32` (NumPy/CuPy, `ac_fast_binomial`). | Documentarlo en el informe (el estado es entero; la precisión solo afecta al cálculo de probabilidades). G8 es "recomendada", no obligatoria. | No. |

### Correspondencia de nombres (para el README y el informe)

| Guía (§6.1) | Este repositorio |
|---|---|
| `python/comun.py` | `python/domain/constants.py`, `python/domain/enums.py` |
| `python/01_secuencial.py` | `python main.py pure` (`adapters/utils_pure.py`) |
| `python/02_numpy.py` | `python main.py numpy` (`adapters/utils_npcp.py`) |
| `python/03_paralelo_cpu.py` | `python main.py multiprocessing` (`adapters/utils_parallel.py`) |
| `python/04_cupy.py` | `python main.py cupy` (`adapters/utils_npcp.py`) |
| `python/05_cupy_rawkernel.py` o `cuda/kernel.cu` | TODO (Daniel) |
| `cpp/*.cpp`, `cpp/Makefile` | igual |
| `resultados/tiempos.csv` | `outputs/times.csv` (+ `outputs/tiempos.csv` derivado) |
| `resultados/validacion/` | `outputs/metrics/` + `outputs/validation_summary.csv` |
| `resultados/figuras/` | `outputs/figures/` |
| `notebooks/analisis.ipynb` | igual |

## 3. Decisiones tomadas en C++ que se apartan de lo conversado (con justificación)

1. **Un flujo aleatorio por fila** (no "semilla + id de hilo"). Serial, OpenMP y
   MPI producen el mismo CSV de métricas para la misma semilla, con cualquier
   número de hilos/procesos; la corrección del paralelismo se verifica con `cmp`.
   Cumple §6.4 ("flujos independientes por proceso, hilo o realización").
2. **Muestreo Binomial exacto** (`std::binomial_distribution`), igual que
   `utils_pure.py` (`random.binomialvariate`), no la aproximación Poisson/Normal
   de NumPy. `AGENTS.md` §7.1 lo permite si se documenta el generador.
3. **`lgamma` reentrante**: evita contención entre hilos (medición en
   `outputs/experiments/`). Responde la pregunta 7 de §6.7.
4. **"18 columnas" de `AGENTS.md` §9.1**: la tabla lista 19 nombres
   (`paradigm, region, fecha` + 16). Se usa el formato real que escribe `main.py`.
5. **Andina**: `AGENTS.md` §7.1 dice L = 168, pero los datos y §8.2 dan L = 154. Se usa 154.

## 4. Pendientes por responsable

- **Daniel**: D3 (tiempos de transferencia en CuPy, sincronización), D4 (kernel
  CUDA), correr CuPy/CUDA 5 veces por región, confirmar D1, D5, D6 y D8.
- **Samuel**: C++ (hecho), multiprocessing (hecho), README, notebook,
  borrador del informe, presentación.
- **Todos**: medir en una sola máquina por paradigma y registrar el hardware
  (D9); "esa página que dijo el profesor" para el informe (confirmar cuál es).
