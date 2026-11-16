# Presentación — guion diapositiva por diapositiva

> Generado por `tools/build_presentacion.py` (no editar a mano: edite el script y vuelva a generarlo).
> Sin código en las diapositivas: hallazgos y parámetros. Las cifras salen de las tablas del notebook.
> Mediciones de CPU: Intel(R) Xeon(R) Processor @ 2.10GHz (4 núcleos, 15Gi RAM) (2026-11-16). Duración sugerida: 12–15 minutos.

## Diapositiva 1 — Paralelización de un modelo de malaria en Colombia

*Un solo problema, ocho formas de ejecutarlo: de Python puro a la GPU*


**Notas del orador:** Presentarse. Frase de apertura acordada: «Usamos un modelo preliminar hecho por Daniel en su curso de fundamentos, con datos reales de malaria en Colombia. Como construir ese modelo no era el objetivo de ESTE curso, nos enfocamos en ejecutarlo en menos tiempo, entendiendo el problema que íbamos a resolver».

## Diapositiva 2 — ¿Qué hace el modelo?

- Simula mes a mes (2007–2023) cómo se contagian humanos y mosquitos en una región de Colombia
- La región es una cuadrícula: cada celda representa 1 000 personas y hasta 2 000 mosquitos
- Dos especies del parásito: P. falciparum y P. vivax (esta con recaídas)
- El clima del mes regula cuántos mosquitos nacen y cuánto transmiten
- Es aleatorio: cada ejecución es una «tirada de dados» distinta

**Cifras destacadas:** **204** meses simulados · **10** tableros por región · **8** sorteos por celda y paso

**Notas del orador:** Humanos: susceptible → infectado → recuperado → susceptible. Mosquitos: susceptible → infectado, hasta morir. Cada celda mira a sus 8 vecinas. 4 sub-pasos por mes.

## Diapositiva 3 — ¿Para qué sirve?

- Explorar cómo responde la transmisión al clima en cada región natural
- Comparar el comportamiento de las dos especies
- Estimar incertidumbre: al ser aleatorio hay que repetirlo muchas veces
- Por eso importa el tiempo: una simulación es barata; cientos de réplicas, no

**Cifras destacadas:** **67 %** variación entre réplicas cerca del umbral

**Figura:** `outputs/figures/P3_variabilidad_replicas.png`

**Notas del orador:** No es predictivo: no incluye tratamiento ni control del mosquito, así que el nivel simulado queda muy por encima del real. Caso más variable: P. falciparum en Pacífico.

## Diapositiva 4 — ¿Por qué este modelo?

- La malaria no se contagia de persona a persona: hace falta el mosquito → modelo de Ross-Macdonald
- Usa datos reales de Colombia: clima, población e incidencia
- Tiene los dos patrones clásicos de paralelismo: una malla con vecinos y réplicas independientes
- Cinco regiones = cinco tamaños de problema para estudiar la escalabilidad

**Cifras destacadas:** **900** celdas · Amazonía · **7 569** celdas · Pacífico · **23 716** celdas · Andina

**Notas del orador:** Para el curso lo importante es la última parte: el problema tiene la forma que permite comparar memoria compartida, memoria distribuida, procesos independientes y GPU.

## Diapositiva 5 — ¿Cómo lo usamos?

- Mismo problema, mismos parámetros y mismos datos en todas las versiones
- Todas escriben los mismos archivos de tiempos y de resultados
- 1 ejecución de calentamiento + 5 repeticiones → mediana
- Solo se cronometra el bucle de los 204 meses
- Equipo: Intel(R) Xeon(R) Processor @ 2.10GHz (4 núcleos, 15Gi RAM)

**Cifras destacadas:** **7** implementaciones medidas · **4** núcleos físicos · **5** repeticiones por configuración

**Notas del orador:** Regiones y tamaños: Amazonía L=30, Orinoquía 39, Pacífico 87, Caribe 96, Andina 154. Todos los núcleos del equipo son equivalentes (procesador homogéneo).

## Diapositiva 6 — ¿Cómo sabemos que todas hacen lo mismo?

- Invariantes: susceptibles + infectados + recuperados = población, en cada mes
- Exacto: C++ secuencial, OpenMP y MPI dan el MISMO resultado con cualquier número de hilos o procesos
- Estadístico: entre lenguajes se comparan promedios de varias réplicas (± 2 errores estándar)

**Cifras destacadas:** **115/115** archivos que cumplen los invariantes · **99 %** meses de C++ dentro de la banda de referencia

**Figura:** `outputs/figures/G2_validacion_amazonia.png`

**Notas del orador:** El nivel exacto es posible porque cada FILA del tablero tiene su propio flujo de números aleatorios. La validación detectó dos efectos reales: un sesgo de ~0,03 % en el generador binomial estándar de C++ y una desviación grande del muestreo aproximado de NumPy cerca del umbral (P. falciparum en Pacífico: +582 % en el tamaño final y 0 % de los meses dentro de la banda).

## Diapositiva 7 — Python puro y NumPy: las referencias

**Parámetros:** Workers: 1 · Python puro: bucles celda a celda · NumPy: tablero completo de una vez · Muestreo NumPy: aproximado

- Python puro es la referencia de corrección; solo se mide en tableros pequeños
- NumPy es 17,8 veces más rápido que Python puro
- NumPy es más rápido que C++ secuencial (3,57 s vs 17,38 s en Pacífico): su muestreo aproximado es más barato

**Cifras destacadas:** **×17,8** NumPy vs Python puro · **×4,9** NumPy vs C++ secuencial

**Figura:** `outputs/figures/P1_paradigmas_por_region.png`

**Notas del orador:** Ojo: la ventaja de NumPy sobre C++ no es del lenguaje sino del algoritmo de muestreo, y tiene un costo en fidelidad cerca del umbral epidémico.

## Diapositiva 8 — Python en paralelo: multiprocessing

**Parámetros:** Estrategia 1 (guía): réplicas completas · Estrategia 2: franjas + memoria compartida · Procesos: 1 … 4 · Réplicas: R = 8

- Réplicas: cada proceso corre simulaciones enteras, sin comunicarse. T₁ = las mismas 8 réplicas con 1 proceso
- Franjas: una simulación repartida por filas, con memoria compartida y una barrera por sub-paso
- Franjas con p = 4 en Amazonía: speedup ×2,90 (eficiencia 0,73)

**Cifras destacadas:** **×3,94** speedup con 4 procesos · **0,98** eficiencia · **0,995** fracción paralela (Amdahl)

**Figura:** `outputs/figures/G5_escalabilidad_fuerte_pacifico.png`

**Notas del orador:** La guía dice que el nivel natural para multiprocessing son las réplicas; aun así medimos también las franjas (descomposición de dominio con memoria compartida) para compararlas. En Amazonía, con p = 4, la estrategia de franjas alcanzó un speedup de 2,90 (eficiencia 0,73, f de Amdahl 0,876), frente a 3,77 (eficiencia 0,94) del ensamble de réplicas. Las franjas pagan 816 barreras por simulación y un registro mensual secuencial; a cambio aceleran UNA simulación.

## Diapositiva 9 — C++ secuencial: la línea base justa

**Parámetros:** Compilación: g++ -O3 · Workers: 1 · Muestreo: binomial exacto

- Mismo algoritmo que Python puro, compilado
- Es el T₁ de OpenMP, MPI y GPU: compara paralelismo, no lenguajes
- El costo crece como L²: pendiente medida 1,75

**Cifras destacadas:** **×5,7** más rápido que Python puro · **17,38 s** una simulación de Pacífico

**Figura:** `outputs/figures/G3_tiempo_vs_tamano.png`

**Notas del orador:** Si comparáramos OpenMP contra Python puro el speedup sería enorme pero engañoso: mezcla lenguaje y paralelismo.

## Diapositiva 10 — OpenMP: memoria compartida

**Parámetros:** Se reparte: filas del tablero · Hilos: 1 … 4 · Scheduling: static · se midieron 3 · Carreras: doble tablero

- Cada hilo lee del tablero actual y escribe solo en sus filas del siguiente
- Los totales se acumulan con reducciones
- Scheduling: en Pacífico, dynamic fue el más rápido (16 % de diferencia frente a static)

**Cifras destacadas:** **×3,17** speedup con 4 hilos · **0,79** eficiencia · **0,915** fracción paralela (Amdahl)

**Figura:** `outputs/figures/G5_escalabilidad_fuerte_pacifico.png`

**Notas del orador:** Karp-Flatt en OpenMP: crece de 0,043 (p = 2) a 0,088 (p = 4). dynamic fue un 16 % más rápido que static en Pacífico, lo que indica que la carga por fila no es uniforme: el costo del muestreo binomial depende del estado epidémico de cada celda y, en un equipo compartido, de la disponibilidad de cada núcleo

## Diapositiva 11 — El freno oculto de OpenMP

- Síntoma: OpenMP escalaba peor que MPI en la misma máquina
- Causa: una función matemática de la biblioteca (lgamma) escribe una variable global que comparten todos los hilos
- Los procesos de MPI no comparten memoria: no lo sufren
- Solución: la versión sin estado compartido (lgamma_r). Mismos resultados

**Cifras destacadas:** **×2,57** speedup antes · **×3,17** speedup después (4 hilos, Pacífico)

**Figura:** `outputs/figures/P4a_lgamma.png`

**Notas del orador:** Es la decisión de implementación con más impacto. Lección: el cuello de botella puede estar en estado compartido escondido dentro de una biblioteca.

## Diapositiva 12 — MPI: memoria distribuida

**Parámetros:** Se reparte: franjas de filas · Procesos: 1 … 4 · Comunicación: solo filas de borde · Frecuencia: 4 veces por mes

- Cada proceso habla con 2 vecinos, en anillo; las filas sobrantes se reparten de a una
- Los totales se combinan con una reducción colectiva
- Escalabilidad débil: eficiencia 0,81 con 4 procesos

**Cifras destacadas:** **×3,53** speedup con 4 procesos · **0,88** eficiencia · **0,955** fracción paralela (Amdahl)

**Figura:** `outputs/figures/G6_escalabilidad_debil.png`

**Notas del orador:** Se envían 6 filas por dirección (humanos infectados, mosquitos infectados y susceptibles, de las dos especies). El tiempo reportado es el del proceso más lento. Karp-Flatt en MPI: disminuye de 0,076 (p = 2) a 0,044 (p = 4).

## Diapositiva 13 — GPU: CuPy y CUDA

**Parámetros:** Qué corre en GPU: pendiente (Daniel) · Tipo de dato: pendiente (Daniel) · Transferencias: pendiente (Daniel)

- Tiempo de copia a la GPU, cómputo y copia de vuelta: pendiente (Daniel)
- Tamaño a partir del cual la GPU supera a la CPU: pendiente (Daniel)
- Kernel CUDA (punto extra): pendiente (Daniel)

**Cifras destacadas:** **—** speedup GPU vs C++ secuencial · **—** fracción de transferencia

**Figura:** `outputs/figures/G7_desglose_gpu.png`

**Notas del orador:** TODO (Daniel). La GPU se mide en otro equipo (Colab): indicarlo en la diapositiva.

## Diapositiva 14 — Tiempo frente a tamaño

- En Andina: NumPy (6,89 s) < MPI (12,42 s) < OpenMP (13,16 s) < C++ secuencial (45,59 s)

**Cifras destacadas:** **×3,67** máximo vs C++ secuencial · MPI con p = 4 en Andina · **×3,86** máximo vs NumPy · multiprocessing con p = 4 en Pacífico

**Figura:** `outputs/figures/G3_tiempo_vs_tamano.png`

**Notas del orador:** Pendientes log-log medidas: NumPy: 1,18; C++ secuencial: 1,75; OpenMP: 1,72; MPI: 1,68. Los puntos huecos de Python puro son extrapolados.

## Diapositiva 15 — ¿Hasta dónde escala?

- Con más workers que núcleos el tiempo no mejora
- MPI: la comunicación pesa más en tableros pequeños y con más procesos

**Cifras destacadas:** **0,915** fracción paralela OpenMP · **0,955** fracción paralela MPI · **0,995** fracción paralela multiprocessing

**Figura:** `outputs/figures/G5_escalabilidad_fuerte_pacifico.png`

**Notas del orador:** Sobresuscripción medida: OpenMP con p = 8: speedup 3,05; multiprocessing con p = 8: speedup 3,92. Todos los núcleos del equipo son equivalentes (procesador homogéneo).

## Diapositiva 16 — ¿Cuándo usar cada técnica?

- **multiprocessing:** Muchas réplicas o barridos de parámetros. Sin comunicación, casi lineal.
- **OpenMP:** Una simulación exacta en un computador multinúcleo. Mínimo esfuerzo.
- **MPI:** Tableros que no caben en un equipo, o un clúster.
- **GPU:** Tableros muy grandes con operaciones uniformes. pendiente (Daniel).
- **NumPy:** Prototipo rápido. Validar cerca del umbral epidémico.

**Notas del orador:** El problema está limitado por el cómputo (el sorteo aleatorio), no por la memoria: los tableros caben en caché.

## Diapositiva 17 — Conclusiones

- **1:** El mismo modelo corre en 7 paradigmas con resultados verificados.
- **2:** Speedup máximo ×3,67 vs C++ secuencial y ×3,86 vs NumPy, con 4 núcleos.
- **3:** La referencia importa: NumPy vs C++ mide sobre todo el algoritmo de muestreo.
- **4:** Paralelizar bien exigió cuidar los números aleatorios y el estado compartido.
- **5:** Medir sin validar no sirve: la versión más rápida fue la menos fiel cerca del umbral.

**Notas del orador:** Limitaciones: tableros pequeños, MPI en un solo equipo, CPU y GPU en máquinas distintas, modelo sin control ni tratamiento.

## Diapositiva 18 — Demostración en vivo y preguntas

*CuPy · C++ con MPI en varios procesos · todas las figuras salen de notebooks/analisis.ipynb*


**Notas del orador:** Comandos de la demo en docs/CHECKLIST_REVISION.md. Repositorio: github.com/dsolartec/hpc-final-project

---

## Preguntas que debemos dominar (lista de Daniel)

- **¿Por qué una forma de paralelizar es más o menos eficiente?** Depende de cuánto trabajo es independiente y cuánto cuesta coordinar: comunicación (MPI), arranque y copia entre procesos (multiprocessing), estado compartido (OpenMP), transferencias (GPU).
- **¿Cuándo usar una forma y cuándo no?** Ver la diapositiva «¿Cuándo usar cada técnica?».
- **¿Cómo se comporta la paralelización en CPU?** Escala hasta el número de núcleos físicos; más allá no mejora. Pocos workers «pesados», cada uno con mucho trabajo.
- **¿Cómo se comporta en GPU?** TODO (Daniel): miles de hilos ligeros; rinde con tableros grandes; paga transferencias.
- **¿Qué hace diferente a cada herramienta?** NumPy vectoriza en un núcleo; multiprocessing usa procesos sin memoria compartida; OpenMP usa hilos con memoria compartida; MPI usa procesos que se envían mensajes; CuPy/CUDA usan la GPU.

## 15 preguntas probables del profesor, con respuestas cortas

1. **¿Qué hace el modelo, en una frase?**
   Simula mes a mes el contagio de malaria entre humanos y mosquitos en una cuadrícula, usando el clima real de cada región de Colombia.

2. **¿Por qué un modelo de Ross-Macdonald y no un SIR clásico?**
   Porque la malaria se transmite por un vector: el humano solo se infecta por el mosquito y el mosquito solo por el humano. El SIR clásico supone contagio directo.

3. **¿Por qué el IPA simulado es tan superior al real?**
   El modelo no incluye diagnóstico, tratamiento ni control del mosquito: simula transmisión libre. Sirve para estudiar la dinámica, no para pronosticar.

4. **¿Qué son speedup y eficiencia?**
   Speedup = tiempo de referencia / tiempo paralelo. Eficiencia = speedup / número de workers; 1 significa aprovechamiento perfecto.

5. **¿Respecto a qué calculan el speedup?**
   Dos referencias: C++ secuencial (comparación justa entre paradigmas) y NumPy (ganancia práctica para quien usa Python). En multiprocessing, el mismo lote de réplicas con 1 proceso.

6. **¿Qué dice la ley de Amdahl y qué fracción paralela obtuvieron?**
   Que el speedup está limitado por la parte que no se paraleliza: S = 1 / ((1 − f) + f/p). Obtuvimos f = [RESULTADO].

7. **¿Diferencia entre Amdahl y Gustafson?**
   Amdahl fija el tamaño del problema (escalabilidad fuerte); Gustafson lo hace crecer con los procesadores (escalabilidad débil), y por eso predice speedups mayores.

8. **¿Qué scheduling usaron en OpenMP y por qué?**
   Partimos de static porque todas las filas tienen el mismo número de celdas (sin costo de planificación, buena localidad). Lo medimos contra dynamic y guided: [RESULTADO]. Si dynamic gana, es porque el costo del sorteo depende del estado de cada celda y la carga por fila no es uniforme.

9. **¿Cómo evitan las condiciones de carrera?**
   Con doble tablero: todos leen del tablero actual y cada hilo escribe solo en sus filas del siguiente. No hay bloqueos. Además, cada fila tiene su propio generador aleatorio.

10. **¿Qué se comunica en MPI y con qué frecuencia?**
   Solo las filas de borde (6 filas por dirección) con los dos procesos vecinos, antes de cada uno de los 4 sub-pasos del mes, con envío y recepción combinados.

11. **¿Qué cambiaría en un clúster real?**
   Los mensajes irían por red, con latencia mucho mayor. Como son mensajes pequeños y frecuentes, la comunicación pesaría más en tableros pequeños; convendría tableros grandes o intercambiar con menos frecuencia.

12. **¿Por qué en multiprocessing paralelizan réplicas y no el tablero?**
   El modelo es aleatorio y necesita muchas réplicas; son independientes y no requieren comunicación. Partir el tablero entre procesos de Python costaría más en comunicación que lo que ahorra.

13. **¿Cómo manejan los números aleatorios en paralelo?**
   Flujos independientes y semillas documentadas: en C++ un flujo por fila del tablero; en multiprocessing, una semilla distinta por réplica. Nunca se comparte un generador ni se repiten semillas.

14. **¿Cómo saben que las versiones paralelas son correctas?**
   Tres niveles: invariantes de conservación, igualdad exacta entre las versiones de C++ y comparación estadística entre lenguajes con varias réplicas.

15. **¿Qué paradigma recomendarían a un epidemiólogo?**
   Para estudiar incertidumbre con muchas réplicas, el ensamble con procesos. Para una simulación grande en un solo equipo, OpenMP. MPI o GPU solo cuando el tablero crezca mucho. [RESULTADO: confirmar con datos]
