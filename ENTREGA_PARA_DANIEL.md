# Entrega para Daniel — qué hay, por qué está así y cómo correrlo en tu Mac

Esta carpeta se copia **encima** de tu repo (misma estructura, no reorganiza nada).
Contiene lo que pediste el 14 de noviembre y lo necesario para correrlo todo con un comando.

> **Importante:** todo se probó de punta a punta en Linux (contenedor de 4 núcleos). **No se
> pudo probar en macOS.** Dejé el Makefile y los scripts preparados para Apple Silicon, pero
> la primera corrida en tu Mac hazla en modo rápido (paso 2) por si hay que ajustar algo.
> Los números que ves en `informe.pdf` y en las diapositivas son de ese contenedor: se
> reemplazan solos cuando corras todo en tu equipo.

---

## 1. Lo que pediste y dónde está

| Pediste | Dónde está | Por qué está hecho así |
|---|---|---|
| **C++ secuencial** | `cpp/secuencial.cpp` + `cpp/common.hpp` | Port directo de `utils_pure.py` (no de NumPy), como dice AGENTS.md. Nombres de archivo exactos de la guía §6.1. `paradigm="serial"`, `workers=1`. Es la línea base justa para OpenMP, MPI y tu kernel. |
| **C++ OpenMP** | `cpp/openmp.cpp` | `parallel for` sobre las filas, doble buffer (sin carreras, sin locks), reducciones para los totales. Hilos con `OMP_NUM_THREADS` (como pide la guía §6.3) o `--threads`. Scheduling configurable con `--schedule` para poder **justificarlo con una medición** (guía §6.3 y pregunta 7 de §6.7). |
| **C++ MPI** | `cpp/mpi.cpp` | Franjas de filas con filas fantasma, `MPI_Sendrecv` entre vecinos en anillo (toroide), `MPI_Reduce` para totales, `MPI_Barrier` y tiempo del proceso más lento (guía §6.4). Reparte las filas sobrantes cuando L no es divisible. Solo el rank 0 escribe. |
| **Makefile** | `cpp/Makefile` | `make`, `make secuencial/openmp/mpi`, `make clean`. `-O3 -std=c++17 -Wall -Wextra -Wpedantic`, sin warnings. Detecta macOS y usa el GCC de Homebrew. |
| **Elegir multiprocessing, joblib o Dask** | `main.py multiprocessing` con **dos estrategias**: `replicas` (`python/adapters/utils_parallel.py`, por defecto) y `franjas` (`python/adapters/utils_mp.py`, el código de Juan Esteban) | **multiprocessing** (librería estándar, sin dependencias). Por defecto, **réplicas** Monte Carlo (R = 8) entre p procesos, porque la guía §5.6 paso 5 dice literal: *"El nivel natural para multiprocessing, joblib o Dask es el de las realizaciones… cada tarea corre una simulación completa"*. El código de Juan (franjas de filas con memoria compartida y barreras) **es correcto** y se conserva como segunda estrategia (`--estrategia franjas`, `paradigm="multiprocessing_franjas"`) para comparar ambos esquemas, como pide la guía para MPI (paso 8). Speedup honesto en ambas: T₁ = el mismo trabajo con 1 proceso. |
| **Notebook con gráficas y comparaciones** | `notebooks/analisis.ipynb` | Genera **todas** las figuras de la guía §6.6 (G1–G7) y las propias de §5.8, en `outputs/figures/`. Si faltan filas de CuPy/CUDA no se rompe: omite esa figura y avisa. |
| **Informe** | `informe.pdf` (raíz, como pide la guía §6.1) | Se genera desde `docs/informe_plantilla.md`: **ningún número está escrito a mano**, todos salen de las tablas del notebook. Estructura de la guía §6.7 y responde sus 8 preguntas. Lo tuyo (GPU) está marcado en amarillo. |
| **Presentación** | `docs/presentacion.pptx` + `docs/presentacion.md` (guion con notas) | Sin código, con parámetros y hallazgos, como dijiste. Incluye tus 4 preguntas de contexto, una diapositiva por técnica, tus 5 preguntas de fondo y 15 preguntas probables con respuesta. Las cifras también salen solas de las tablas. |
| **Kernel CUDA / CuPy** | — | **No los toqué.** Quedan como `TODO (Daniel)` en README, informe y presentación. |

Extras que hicieron falta para cumplir la guía (no los pediste, pero sin ellos no se puede validar ni medir):
`tools/` (benchmarks, validación, generadores) y `docs/` (acuerdos con la guía y lista de revisión).

---

## 2. Cómo correrlo en tu Mac (M1 Pro)

**Preparación (una sola vez):**

```bash
brew install gcc open-mpi pandoc
```

```bash
cd python && poetry install && poetry run pip install jupyter python-pptx && source "$(poetry env info --path)/bin/activate" && cd ..
```

El `g++` de Apple es clang y no trae OpenMP: el Makefile busca solo el `g++-NN` de Homebrew
y hace que `mpicxx` lo use. Para ver qué compilador tomó:

```bash
make -C cpp info
```

**Prueba rápida (unos 3–5 minutos, solo amazonia, 2 repeticiones):**

```bash
RAPIDO=1 bash tools/run_all.sh
```

**Medición completa (5 repeticiones; detecta los 10 núcleos y usa p = 1, 2, 4, 8, 10):**

```bash
bash tools/run_all.sh
```

Hace, en orden: datos → compila → C++ (serial, OpenMP, MPI) → escalabilidad débil,
scheduling y `lgamma` → NumPy, Python puro y multiprocessing → validación → notebook →
`informe.pdf` → `presentacion.pptx`. Deja el hardware en `outputs/hardware.txt`.
**Borra `outputs/times.csv` y las métricas anteriores** para no mezclar equipos (`LIMPIAR=0` lo evita).
En el contenedor de 4 núcleos la medición completa tardó cerca de una hora; en tu Mac no lo he medido.

Si algo de macOS falla:

| Síntoma | Solución |
|---|---|
| `unsupported option '-fopenmp'` | Está usando clang: `make -C cpp CXX=g++-14` (pon tu versión). |
| Error con `-mcpu=native` | `make -C cpp NATIVE=` |
| No se genera el PDF | Necesita Google Chrome en `/Applications`. Si no, abre `docs/informe.html` e imprime a PDF. |
| `mpirun` se queja de slots | `PROCS="1 2 4 8" THREADS="1 2 4 8 10" bash tools/benchmark_cpp.sh amazonia pacifico` |

**Después de añadir tus filas de CuPy/CUDA** a `outputs/times.csv`, solo repite el final:

```bash
python -m jupyter execute --inplace notebooks/analisis.ipynb && python tools/build_informe.py && python tools/build_presentacion.py
```

---

## 3. Lo que cambié de lo tuyo y por qué

| Archivo tuyo | Cambio | Por qué |
|---|---|---|
| `python/main.py` | Solo **añadí** el subcomando `multiprocessing` con sus dos estrategias (y los imports). No toqué `pure`, `numpy` ni `cupy`. | Es lo que pediste; mismo formato de `times.csv` y métricas. |
| `python/adapters/utils_mp.py` (de Juan) | Lo dejé casi igual. Tres cambios: (1) las esperas del proceso principal en las barreras tienen tiempo límite, porque si un proceso moría al arrancar el programa se quedaba **colgado para siempre** (lo comprobé); (2) el mensaje de error dice qué procesos fallaron; (3) docstring que explica su papel frente a la estrategia de réplicas. | Lo validé: conserva la población los 204 meses y su tamaño epidémico coincide con Python puro. En amazonia, 4 procesos: speedup ≈ 2,9 frente a 3,8 de las réplicas. |
| Handler de Juan en su `main.py` | Lo integré como `--estrategia franjas`, con `--runs` (antes cada ejecución **sobrescribía** el CSV de métricas y no había réplicas para validar) y semillas distintas por réplica. | Sin réplicas no se puede hacer la validación estadística de la guía §5.7. |
| `python/README.md` | Rellené el TODO de "paralelo CPU". El de CuPy quedó `TODO (Daniel)`. | Era el TODO que dejaste. |
| `README.md` | Rellené el TODO de C++ y añadí análisis y documentación. CUDA quedó `TODO (Daniel)`. | Guía §6.9: "el README permite a otra persona compilar y ejecutar todo desde cero". |
| `.gitignore` | **Añadí** líneas para los binarios de C++ y la animación de multiprocessing. No quité ninguna tuya. | Para no subir ejecutables. |
| `utils_pure.py`, `utils_npcp.py`, `utils_animations.py`, `constants.py`, `enums.py`, `AGENTS.md` | **Nada.** | — |

No reorganicé la estructura. Tu `main.py` con subcomandos y `outputs/` se quedan; en el README
hay una tabla que mapea los nombres de la guía (`01_secuencial.py`, `resultados/`…) a los tuyos.

---

## 4. Decisiones que te pueden sorprender (y su justificación)

1. **Un generador aleatorio por fila del tablero, no por hilo.** Así serial, OpenMP y MPI dan
   el **mismo CSV de métricas** con cualquier número de hilos o procesos (se comprueba con
   `cmp`). La guía §6.4 pide "flujos independientes por proceso, hilo o realización": se
   cumple, y además la corrección del paralelismo deja de ser estadística.
2. **Binomial exacta en C++** (`std::binomial_distribution`), igual que `utils_pure.py`, no la
   aproximación de NumPy. AGENTS.md §7.1 lo permite si se documenta. Consecuencia: **NumPy en
   un núcleo es más rápido que C++ secuencial**, porque su muestreo es más barato. Está
   explicado en el informe §7.1; no es un bug.
3. **`lgamma` reentrante** en `common.hpp`. La binomial de la librería estándar llama a
   `lgamma()`, que escribe una variable global; con varios hilos eso frenaba a OpenMP
   (speedup 2,6 → 3,2 con 4 hilos en pacifico). Es la respuesta medida a la pregunta 7 de §6.7.
4. **`--board-size`** en los binarios: solo para la gráfica obligatoria G6 (escalabilidad
   débil de MPI, tamaño proporcional a p). Las corridas normales usan el L de la región.
5. **`times.csv` se queda con tus 8 columnas.** La guía §6.4 pide otras (`repeticion`,
   `precision`, `equipo`…): el notebook las deriva en `outputs/tiempos.csv`, sin tocar tu formato.
6. AGENTS.md dice "18 columnas" en las métricas, pero tu `main.py` escribe 19 nombres
   (`paradigm, region, fecha` + 16). Usé el formato real. Y §7.1 dice Andina L = 168; los
   datos y §8.2 dan 154: usé 154.

---

## 5. Lo que te toca a ti (según la guía)

1. **CuPy debe medir por separado** copia a GPU, cómputo y copia de vuelta, sincronizando
   antes de parar el reloj (guía §6.2 y §6.4). De ahí sale la gráfica obligatoria **G7**. Hoy
   `handle_cupy` mide un solo tiempo. Propuesta para no romper `times.csv`: un archivo nuevo
   `outputs/times_gpu.csv` con `paradigm,region,board_size,t_h2d,t_compute,t_d2h`; el
   notebook ya lo lee si existe.
2. **Kernel CUDA:** la guía (§1.2 ítem 8 y §6.2) acepta `cupy.RawKernel` desde Python, no
   hace falta `nvcc` ni C++. La regla de una celda está aislada en `step_row()` de
   `cpp/common.hpp` por si la quieres portar.
3. **Revisa el muestreador de NumPy/CuPy cerca del umbral.** En pacifico, *P. falciparum*
   con `ac_fast_binomial` da un tamaño epidémico ~6,8 veces mayor que Python puro (0 % de los
   meses dentro de la banda). Hipótesis sin confirmar: decide Poisson/Normal con el
   **máximo** de n·p de todo el tablero, y la normal redondeada infla los conteos bajos. Está
   en el informe §6.2 como hallazgo; tú decides si se corrige o se documenta.
4. Rellenar lo amarillo del informe (GPU, horas de trabajo) y la guía de CuPy/CUDA en los README.
5. **Tu Mac tiene 8 núcleos rápidos y 2 lentos.** Con 10 workers y reparto estático el
   tiempo lo marca el núcleo lento: es esperable que la eficiencia caiga de p = 8 a p = 10 y
   que `dynamic` gane. El informe ya lo explica solo si `hardware.txt` lo detecta.

Más detalle: `docs/ACUERDOS_GUIA_VS_REPO.md` (guía vs. repo, punto por punto) y
`docs/CHECKLIST_REVISION.md` (comandos, resultados esperados y de dónde sale cada número).
