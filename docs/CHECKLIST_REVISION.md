# Lista de revisión final

Para quien revise el trabajo al final: comandos exactos, qué debe salir en cada uno y de
dónde sale cada número del informe. Todos los comandos se ejecutan **desde la raíz del
repositorio** salvo que se indique otra carpeta.

> **Los valores "preliminares" de este documento se midieron en un contenedor en la nube**
> (Intel Xeon 2,10 GHz, 4 núcleos, 15 GB RAM, g++ 13.3, Open MPI 4.1.6, Python 3.13).
> Sirven para comprobar que todo funciona y el orden de magnitud. **Los números definitivos
> se miden en el equipo de Daniel** (MacBook Pro M1 Pro: 10 núcleos físicos, 8 de alto
> rendimiento y 2 de eficiencia, 16 GB) con `bash tools/run_all.sh`, que regenera
> `outputs/hardware.txt`, las figuras, `informe.pdf` y la presentación. En ese equipo los
> workers son p = 1, 2, 4, 8, 10. El flujo se probó completo en Linux; **en macOS no se ha probado**.

## 0. Requisitos

Linux / WSL:

```bash
sudo apt install build-essential openmpi-bin libopenmpi-dev pandoc
```

macOS:

```bash
brew install gcc open-mpi pandoc
```

Python (entorno del proyecto activado; los scripts usan `python3`, cámbielo con `PY=` y `PYTOOLS=`):

```bash
cd python && poetry install && poetry run pip install jupyter python-pptx && source "$(poetry env info --path)/bin/activate" && cd ..
```

## 0.1 Todo con un comando

```bash
RAPIDO=1 bash tools/run_all.sh
```
Prueba rápida (preliminar: ~3 min): debe terminar con `LISTO` y dejar `informe.pdf`,
`docs/presentacion.pptx` y las figuras en `outputs/figures/`.

```bash
bash tools/run_all.sh
```
Medición completa. Los pasos 1 a 6 de abajo son lo mismo, paso a paso.

## 1. Datos y compilación

```bash
python tools/export_csv.py
```
Debe imprimir: `Escrito data/GAM_regional_enriquecido.csv: 1020 filas, meses por región = {... 204 ...}`.

```bash
make -C cpp clean all
```
Debe compilar `secuencial`, `openmp` y `mpi` **sin ninguna advertencia**.

## 2. Corrección de la paralelización (exacta)

```bash
cd cpp && ./secuencial --region amazonia --warmup 0 --outdir /tmp/chk && ./openmp --region amazonia --threads 4 --warmup 0 --outdir /tmp/chk && mpirun -np 3 ./mpi --region amazonia --warmup 0 --outdir /tmp/chk && cd ..
```

```bash
for p in openmp mpi; do cmp <(cut -d, -f2- /tmp/chk/metrics/serial_amazonia.csv) <(cut -d, -f2- /tmp/chk/metrics/${p}_amazonia.csv) && echo "$p: idéntico a serial"; done
```
Debe imprimir `openmp: idéntico a serial` y `mpi: idéntico a serial`. Para probar el reparto de filas sobrantes repita con `--region pacifico` y `-np 4` (L = 87 no es divisible por 4).

## 3. Benchmarks

| Comando | Qué produce | Duración preliminar |
|---|---|---|
| `bash tools/benchmark_cpp.sh amazonia pacifico` | serial, OpenMP (1, 2, 4, 8) y MPI (1, 2, 4), 5 réplicas | ~12 min |
| `RUNS=5 THREADS=4 PROCS=4 bash tools/benchmark_cpp.sh orinoquia caribe andina` | resto de regiones para G3/G4 | ~15 min |
| `bash tools/benchmark_python_mp.sh amazonia pacifico` | multiprocessing (réplicas) con 1, 2, 4, 8 procesos, 5 repeticiones | ~12 min |
| `ESTRATEGIA=franjas bash tools/benchmark_python_mp.sh amazonia pacifico` | multiprocessing (franjas, código de Juan Esteban) | ~25 min (núcleo de Python puro) |
| `bash tools/benchmark_python_single.sh` | NumPy (5 regiones) y Python puro (amazonia, orinoquia) | ~6 min |
| `bash tools/benchmark_weak.sh` | escalabilidad débil de MPI → `outputs/experiments/weak/` | ~2 min |
| `bash tools/benchmark_schedule.sh` | scheduling de OpenMP → `outputs/experiments/schedule/` | ~2 min |
| `python tools/pure_replicas.py --region amazonia --runs 24` y `--region pacifico --runs 8` | réplicas de referencia de Python puro | ~2 min y ~5 min |

Ajuste `THREADS` y `PROCS` al número de **núcleos físicos** del equipo (guía §1.5).
Antes de la medición definitiva, borre `outputs/times.csv` para no mezclar equipos.

## 4. Validación

```bash
python tools/validate_metrics.py
```
Debe terminar con `N/N archivos válidos` (preliminar: `112/112`).

```bash
python tools/compare_stats.py
```
Escribe `outputs/validation_summary.csv`. **Resultado esperado (preliminar), no todo "True":**

| Región / especie | C++ vs. Python puro | NumPy (multiprocessing) vs. Python puro |
|---|---|---|
| amazonia / vivax | +0,02 %, cumple 2 SE | +0,11 %, no cumple (muestreo aproximado) |
| amazonia / falciparum | −0,18 %, no cumple con n = 5 (cumple con n = 40) | +0,34 %, no cumple |
| pacifico / vivax | +0,02 %, cumple | +0,15 %, no cumple |
| pacifico / falciparum | cumple (varianza enorme: unas réplicas se extinguen) | **+582 %, 0 % de meses en banda** |

Explicación de cada "no cumple" en `docs/informe.md` §6.2. **El último es un problema
real del muestreador aproximado de NumPy/CuPy cerca del umbral de extinción: decidir con
Daniel si se corrige o se documenta.**

```bash
g++ -O3 -std=c++17 tools/binomial_bias_test.cpp -o /tmp/bintest && /tmp/bintest
```
Preliminar: para n = 1000, p = 0,03 → `sesgo_rel=3.83e-04 z=13.5`; para np = 5 y np = 360, |z| < 2.

## 5. Notebook y figuras

```bash
python -m jupyter execute --inplace notebooks/analisis.ipynb
```
Debe terminar sin errores y dejar en `outputs/figures/` 17 figuras (18 con G7 cuando
existan los datos de GPU) y 9 tablas CSV. La última celda lista las figuras y los avisos.
Avisos esperados mientras falte la parte de GPU: `cupy`, `cuda`, G4 (cruce) y G7.

Si se edita el notebook, hágalo en `tools/build_notebook.py` y regenérelo con
`python tools/build_notebook.py`.

## 6. Informe y presentación

```bash
python tools/build_informe.py
```
Debe imprimir `escrito informe.pdf (...)` (preliminar: 24 páginas, 21 marcas pendientes).
Las cifras salen de `outputs/figures/tabla_*.csv` a través de `tools/resultados.py`; el
texto está en `docs/informe_plantilla.md` (los `{{marcadores}}` son los valores medidos).

```bash
python tools/build_presentacion.py
```
Genera `docs/presentacion.pptx` (18 diapositivas) y `docs/presentacion.md`.

```bash
python tools/resultados.py
```
Imprime todas las cifras que se insertan en el informe y en la presentación, para revisarlas.

```bash
grep -n "PENDIENTE\|TODO (Daniel)\|POR VERIFICAR" docs/informe_plantilla.md
```
Lista lo que falta por completar a mano (GPU, horas de trabajo, perfilador, referencias).

## 7. De dónde sale cada número del informe

Todas las cifras de rendimiento salen de `outputs/times.csv` a través del notebook. La
**mediana** de las filas que cumplen el filtro es el valor que se reporta.

| Dato del informe | Filas de `outputs/times.csv` (filtro) | Tabla / figura | Valor preliminar |
|---|---|---|---|
| T serial C++ (§7.1, Tabla 4) | `language=cpp, paradigm=serial, region=R` | `tabla_resumen_tiempos.csv` | amazonia 2,79 s · orinoquia 4,44 · pacifico 17,38 · caribe 25,76 · andina 45,59 |
| T NumPy (§7.1) | `paradigm=numpy, region=R` | ídem | 1,08 · 1,22 · 3,57 · 3,95 · 6,89 s |
| T Python puro (§7.1) | `paradigm=pure, region=R` | ídem; G3 (extrapolados huecos) | amazonia 14,9 s · orinoquia 26,6 s |
| Speedup y eficiencia OpenMP (Tabla 4) | `paradigm=openmp, region=R, workers=p` ÷ serial | `tabla_escalabilidad.csv`, G5 | pacifico: p=2 → 1,92 · p=4 → 3,17 (E = 0,79) |
| Speedup y eficiencia MPI (Tabla 4) | `paradigm=mpi, region=R, workers=p` ÷ serial | ídem | pacifico: p=2 → 1,86 · p=4 → 3,53 (E = 0,88) |
| Speedup multiprocessing (Tabla 4) | `paradigm=multiprocessing, workers=p` ÷ `workers=1` (mismo R = 8) | ídem | pacifico: p=2 → 2,01 · p=4 → 3,94 (E = 0,98) |
| Speedup multiprocessing franjas (§4.2) | `paradigm=multiprocessing_franjas, workers=p` ÷ `workers=1` | ídem | amazonia: p=2 → 1,84 · p=4 → 2,90 (E = 0,73) |
| f de Amdahl (§8.1 p. 2) | las mismas filas, p ≤ núcleos | columna `amdahl_f` | pacifico: OpenMP 0,915 · MPI 0,955 · multiprocessing 0,995 |
| Karp-Flatt (§8.1 p. 2) | ídem | columna `karp_flatt` | pacifico OpenMP: 0,043 (p=2) → 0,088 (p=4): crece |
| Sobresuscripción | `workers=8` (en un equipo de 4 núcleos) | G5 (puntos huecos) | OpenMP pacifico: 3,05 (no mejora) |
| Speedup máximo vs. C++ serial (Resumen, §8.1 p. 1) | mejor config. por región | G4 derecha | MPI p=4, andina: 45,59 / 12,42 = 3,67 |
| Speedup vs. NumPy (Resumen) | ídem ÷ numpy | G4 izquierda | multiprocessing p=4, pacifico: 3,57 / 0,93 = 3,86 por réplica; C++ es más lento que NumPy (ver §7.1) |
| Pendiente log-log (§7.1) | mediana por región | salida de la celda G3 | serial 1,75 · OpenMP 1,72 · MPI 1,68 · NumPy 1,18 |
| Escalabilidad débil (§7.4) | `outputs/experiments/weak/times.csv` | G6 | T = 3,73 s (p=1, L=44) · 4,29 (p=2, L=62) · 4,50 (p=4, L=87) |
| Efecto de `lgamma` (§7.7) | `outputs/experiments/times_cpp_glibc_lgamma.csv` vs. `times.csv`, `openmp, workers=4` | P4a | pacifico: 2,58 → 3,17 · amazonia: 2,14 → 3,40 |
| Scheduling (§4.5, §8.1 p. 7) | `outputs/experiments/schedule/schedule.csv` | P4b | pacifico, 4 hilos: static 4,88 s · dynamic 4,08 · guided 4,31 |
| Validación (§6.2) | `outputs/metrics/*_run*.csv` | `tabla_validacion.csv`, G2 | ver paso 4 |
| Variabilidad entre réplicas y extinción (§6.1) | `outputs/metrics/*_run*.csv` | `tabla_variabilidad.csv`, P3 | pacifico falciparum: CV 67 % (Python puro); extinción solo en andina falciparum |
| Líneas de código (Tabla 5) | `wc -l` | — | ya rellenado en el informe |
| GPU (§4.3, §4.7, §7.5) | `paradigm=cupy/cuda` + `outputs/times_gpu.csv` | G7 | TODO (Daniel) |

## 8. Pendientes antes de entregar

- [ ] Medir todo en el equipo de Daniel con `bash tools/run_all.sh` (5 repeticiones) y revisar que `outputs/hardware.txt` describa ese equipo.
- [ ] Daniel: CuPy/CUDA en `times.csv`, `outputs/times_gpu.csv` (copia a GPU, cómputo, copia de vuelta), guía de CuPy/CUDA en los README.
- [ ] Decidir con Daniel: muestreador aproximado de NumPy/CuPy cerca de la extinción (paso 4).
- [ ] Decidir scheduling por defecto de OpenMP con la medición definitiva (P4b).
- [ ] Acordar los puntos D1, D5, D6 y D8 de `docs/ACUERDOS_GUIA_VS_REPO.md`.
- [ ] Completar lo marcado en amarillo en el informe (`docs/informe_plantilla.md`) y verificar las referencias marcadas.
- [ ] Medir la fracción paralela con un perfilador (`perf` o `gprof`) para §8.1 p. 2, y las horas de trabajo de la Tabla 5.
- [ ] Si el profesor exige "la página" que mencionó para el informe, pasar allí el contenido de `docs/informe.md`.
- [ ] Ensayar la demostración en vivo: `mpirun -np 4 ./mpi --region amazonia` y la versión CuPy (guía §6.8).
- [ ] Cada integrante debe tener commits propios en el repositorio.
