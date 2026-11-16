"""
Genera docs/presentacion.pptx (diseño propio, 16:9) y docs/presentacion.md (guion con notas
del orador) a partir de UNA sola definición de contenido.

- Sin código en las diapositivas: hallazgos y parámetros (acuerdo del grupo).
- Las cifras salen de las tablas del notebook (tools/resultados.py): tras volver a medir,
  ejecute el notebook y luego este script; nada se escribe a mano.
- Las figuras se insertan desde outputs/figures/.

Uso (desde la raíz del repo):  python tools/build_presentacion.py
Requiere: pip install python-pptx
"""
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "outputs" / "figures"
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "tools"))
from resultados import cargar  # noqa: E402

V = cargar()
if V.get("_faltan_tablas"):
    sys.exit("ERROR: faltan las tablas de outputs/figures/. Ejecute primero el notebook.")


def v(k):
    return str(V.get(k, "pendiente"))


RP = v("region_p_nombre")
PEND = "pendiente (Daniel)"

# Cada diapositiva: tipo, kicker (texto pequeño superior), titulo, puntos, kpis [(valor, etiqueta)],
# chips [(clave, valor)] para parámetros, figura y notas del orador.
SLIDES = [
    dict(tipo="portada", t="Paralelización de un modelo de malaria en Colombia",
         sub="Un solo problema, ocho formas de ejecutarlo: de Python puro a la GPU",
         n="Presentarse. Frase de apertura acordada: «Usamos un modelo preliminar hecho por Daniel en su curso de fundamentos, con "
           "datos reales de malaria en Colombia. Como construir ese modelo no era el objetivo de ESTE curso, nos enfocamos en "
           "ejecutarlo en menos tiempo, entendiendo el problema que íbamos a resolver»."),

    dict(tipo="contexto", num="01", k="Contexto", t="¿Qué hace el modelo?",
         p=["Simula mes a mes (2007–2023) cómo se contagian humanos y mosquitos en una región de Colombia",
            "La región es una cuadrícula: cada celda representa 1 000 personas y hasta 2 000 mosquitos",
            "Dos especies del parásito: P. falciparum y P. vivax (esta con recaídas)",
            "El clima del mes regula cuántos mosquitos nacen y cuánto transmiten",
            "Es aleatorio: cada ejecución es una «tirada de dados» distinta"],
         kpis=[("204", "meses simulados"), ("10", "tableros por región"), ("8", "sorteos por celda y paso")],
         n="Humanos: susceptible → infectado → recuperado → susceptible. Mosquitos: susceptible → infectado, hasta morir. Cada celda "
           "mira a sus 8 vecinas. 4 sub-pasos por mes."),

    dict(tipo="contexto", num="02", k="Contexto", t="¿Para qué sirve?",
         p=["Explorar cómo responde la transmisión al clima en cada región natural",
            "Comparar el comportamiento de las dos especies",
            "Estimar incertidumbre: al ser aleatorio hay que repetirlo muchas veces",
            "Por eso importa el tiempo: una simulación es barata; cientos de réplicas, no"],
         kpis=[(v("var_cv") + " %", "variación entre réplicas cerca del umbral")],
         n="No es predictivo: no incluye tratamiento ni control del mosquito, así que el nivel simulado queda muy por encima del real. "
           f"Caso más variable: {v('var_caso').replace('*', '')}.",
         f="P3_variabilidad_replicas.png"),

    dict(tipo="contexto", num="03", k="Contexto", t="¿Por qué este modelo?",
         p=["La malaria no se contagia de persona a persona: hace falta el mosquito → modelo de Ross-Macdonald",
            "Usa datos reales de Colombia: clima, población e incidencia",
            "Tiene los dos patrones clásicos de paralelismo: una malla con vecinos y réplicas independientes",
            "Cinco regiones = cinco tamaños de problema para estudiar la escalabilidad"],
         kpis=[("900", "celdas · Amazonía"), ("7 569", "celdas · Pacífico"), ("23 716", "celdas · Andina")],
         n="Para el curso lo importante es la última parte: el problema tiene la forma que permite comparar memoria compartida, "
           "memoria distribuida, procesos independientes y GPU."),

    dict(tipo="contexto", num="04", k="Contexto", t="¿Cómo lo usamos?",
         p=["Mismo problema, mismos parámetros y mismos datos en todas las versiones",
            "Todas escriben los mismos archivos de tiempos y de resultados",
            "1 ejecución de calentamiento + 5 repeticiones → mediana",
            "Solo se cronometra el bucle de los 204 meses",
            f"Equipo: {v('equipo_corto')}"],
         kpis=[(v("n_paradigmas"), "implementaciones medidas"), (v("nucleos"), "núcleos físicos"), ("5", "repeticiones por configuración")],
         n="Regiones y tamaños: Amazonía L=30, Orinoquía 39, Pacífico 87, Caribe 96, Andina 154. " + v("nota_nucleos").replace("**", "")),

    dict(tipo="contenido", k="Validación", t="¿Cómo sabemos que todas hacen lo mismo?",
         p=["Invariantes: susceptibles + infectados + recuperados = población, en cada mes",
            "Exacto: C++ secuencial, OpenMP y MPI dan el MISMO resultado con cualquier número de hilos o procesos",
            "Estadístico: entre lenguajes se comparan promedios de varias réplicas (± 2 errores estándar)"],
         kpis=[(f"{v('n_validos')}/{v('n_archivos')}", "archivos que cumplen los invariantes"),
               (v("cpp_banda_min") + " %", "meses de C++ dentro de la banda de referencia")],
         n="El nivel exacto es posible porque cada FILA del tablero tiene su propio flujo de números aleatorios. La validación detectó "
           "dos efectos reales: un sesgo de ~0,03 % en el generador binomial estándar de C++ y una desviación grande del muestreo "
           f"aproximado de NumPy cerca del umbral ({v('numpy_peor').replace('*', '')}).",
         f="G2_validacion_amazonia.png"),

    dict(tipo="tecnica", k="Técnica 1", t="Python puro y NumPy: las referencias",
         chips=[("Workers", "1"), ("Python puro", "bucles celda a celda"), ("NumPy", "tablero completo de una vez"),
                ("Muestreo NumPy", "aproximado")],
         p=["Python puro es la referencia de corrección; solo se mide en tableros pequeños",
            f"NumPy es {v('ratio_pure_numpy')} veces más rápido que Python puro",
            f"NumPy es {v('numpy_vs_serial')} que C++ secuencial ({v('t_numpy_p')} s vs {v('t_serial_p')} s en {RP}): su muestreo aproximado es más barato"],
         kpis=[("×" + v("ratio_pure_numpy"), "NumPy vs Python puro"), ("×" + v("ratio_serial_numpy"), "NumPy vs C++ secuencial")],
         n="Ojo: la ventaja de NumPy sobre C++ no es del lenguaje sino del algoritmo de muestreo, y tiene un costo en fidelidad "
           "cerca del umbral epidémico.", f="P1_paradigmas_por_region.png"),

    dict(tipo="tecnica", k="Técnica 2", t="Python en paralelo: multiprocessing",
         chips=[("Estrategia 1 (guía)", "réplicas completas"), ("Estrategia 2", "franjas + memoria compartida"),
                ("Procesos", "1 … " + v("p_mp")), ("Réplicas", "R = 8")],
         p=["Réplicas: cada proceso corre simulaciones enteras, sin comunicarse. T₁ = las mismas 8 réplicas con 1 proceso",
            "Franjas: una simulación repartida por filas, con memoria compartida y una barrera por sub-paso",
            f"Franjas con p = {v('franjas_p')} en {v('franjas_region')}: speedup ×{v('franjas_S')} (eficiencia {v('franjas_E')})"],
         kpis=[("×" + v("S_mp"), f"speedup con {v('p_mp')} procesos"), (v("E_mp"), "eficiencia"), (v("f_mp"), "fracción paralela (Amdahl)")],
         n="La guía dice que el nivel natural para multiprocessing son las réplicas; aun así medimos también las franjas "
           "(descomposición de dominio con memoria compartida) para compararlas. " + v("franjas_resumen") + ". Las franjas "
           "pagan 816 barreras por simulación y un registro mensual secuencial; a cambio aceleran UNA simulación.",
         f=f"G5_escalabilidad_fuerte_{v('region_p')}.png"),

    dict(tipo="tecnica", k="Técnica 3", t="C++ secuencial: la línea base justa",
         chips=[("Compilación", "g++ -O3"), ("Workers", "1"), ("Muestreo", "binomial exacto")],
         p=["Mismo algoritmo que Python puro, compilado",
            "Es el T₁ de OpenMP, MPI y GPU: compara paralelismo, no lenguajes",
            "El costo crece como L²: pendiente medida " + next((x.split(': ')[1] for x in v('pendientes').split('; ') if 'secuencial' in x), '—')],
         kpis=[("×" + v("ratio_pure_serial"), "más rápido que Python puro"), (v("t_serial_p") + " s", f"una simulación de {RP}")],
         n="Si comparáramos OpenMP contra Python puro el speedup sería enorme pero engañoso: mezcla lenguaje y paralelismo.",
         f="G3_tiempo_vs_tamano.png"),

    dict(tipo="tecnica", k="Técnica 4", t="OpenMP: memoria compartida",
         chips=[("Se reparte", "filas del tablero"), ("Hilos", "1 … " + v("p_omp")), ("Scheduling", "static · se midieron 3"),
                ("Carreras", "doble tablero")],
         p=["Cada hilo lee del tablero actual y escribe solo en sus filas del siguiente",
            "Los totales se acumulan con reducciones",
            f"Scheduling: en {RP}, {v('sched_mejor')} fue el más rápido ({v('sched_dif')} % de diferencia frente a static)"],
         kpis=[("×" + v("S_omp"), f"speedup con {v('p_omp')} hilos"), (v("E_omp"), "eficiencia"), (v("f_omp"), "fracción paralela (Amdahl)")],
         n="Karp-Flatt en OpenMP: " + v("kf_omp") + ". " + v("sched_frase").replace("`", "").replace("**", ""),
         f=f"G5_escalabilidad_fuerte_{v('region_p')}.png"),

    dict(tipo="hallazgo", k="Hallazgo", t="El freno oculto de OpenMP",
         p=["Síntoma: OpenMP escalaba peor que MPI en la misma máquina",
            "Causa: una función matemática de la biblioteca (lgamma) escribe una variable global que comparten todos los hilos",
            "Los procesos de MPI no comparten memoria: no lo sufren",
            "Solución: la versión sin estado compartido (lgamma_r). Mismos resultados"],
         kpis=[("×" + v("lgamma_antes"), "speedup antes"), ("×" + v("lgamma_despues"), f"speedup después ({v('lgamma_hilos')} hilos, {RP})")],
         n="Es la decisión de implementación con más impacto. Lección: el cuello de botella puede estar en estado compartido "
           "escondido dentro de una biblioteca.", f="P4a_lgamma.png"),

    dict(tipo="tecnica", k="Técnica 5", t="MPI: memoria distribuida",
         chips=[("Se reparte", "franjas de filas"), ("Procesos", "1 … " + v("p_mpi")), ("Comunicación", "solo filas de borde"),
                ("Frecuencia", "4 veces por mes")],
         p=["Cada proceso habla con 2 vecinos, en anillo; las filas sobrantes se reparten de a una",
            "Los totales se combinan con una reducción colectiva",
            f"Escalabilidad débil: eficiencia {v('debil_E')} con {v('debil_p')} procesos"],
         kpis=[("×" + v("S_mpi"), f"speedup con {v('p_mpi')} procesos"), (v("E_mpi"), "eficiencia"), (v("f_mpi"), "fracción paralela (Amdahl)")],
         n="Se envían 6 filas por dirección (humanos infectados, mosquitos infectados y susceptibles, de las dos especies). El tiempo "
           "reportado es el del proceso más lento. Karp-Flatt en MPI: " + v("kf_mpi") + ".", f="G6_escalabilidad_debil.png"),

    dict(tipo="tecnica", k="Técnica 6", t="GPU: CuPy y CUDA",
         chips=[("Qué corre en GPU", PEND), ("Tipo de dato", PEND), ("Transferencias", PEND)],
         p=["Tiempo de copia a la GPU, cómputo y copia de vuelta: " + PEND,
            "Tamaño a partir del cual la GPU supera a la CPU: " + PEND,
            "Kernel CUDA (punto extra): " + PEND],
         kpis=[("—", "speedup GPU vs C++ secuencial"), ("—", "fracción de transferencia")],
         n="TODO (Daniel). La GPU se mide en otro equipo (Colab): indicarlo en la diapositiva.", f="G7_desglose_gpu.png"),

    dict(tipo="figura", k="Comparación", t="Tiempo frente a tamaño",
         p=[f"En {v('region_grande')}: {v('ranking_grande')}"],
         kpis=[("×" + v("smax_serial"), "máximo vs C++ secuencial · " + v("smax_serial_cfg")),
               ("×" + v("smax_numpy"), "máximo vs NumPy · " + v("smax_numpy_cfg"))],
         n="Pendientes log-log medidas: " + v("pendientes") + ". Los puntos huecos de Python puro son extrapolados.",
         f="G3_tiempo_vs_tamano.png"),

    dict(tipo="figura", k="Comparación", t="¿Hasta dónde escala?",
         p=["Con más workers que núcleos el tiempo no mejora",
            "MPI: la comunicación pesa más en tableros pequeños y con más procesos"],
         kpis=[(v("f_omp"), "fracción paralela OpenMP"), (v("f_mpi"), "fracción paralela MPI"), (v("f_mp"), "fracción paralela multiprocessing")],
         n="Sobresuscripción medida: " + v("sobresuscripcion") + ". " + v("nota_nucleos").replace("**", ""),
         f=f"G5_escalabilidad_fuerte_{v('region_p')}.png"),

    dict(tipo="tarjetas", k="Síntesis", t="¿Cuándo usar cada técnica?",
         cards=[("multiprocessing", "Muchas réplicas o barridos de parámetros. Sin comunicación, casi lineal."),
                ("OpenMP", "Una simulación exacta en un computador multinúcleo. Mínimo esfuerzo."),
                ("MPI", "Tableros que no caben en un equipo, o un clúster."),
                ("GPU", "Tableros muy grandes con operaciones uniformes. " + PEND + "."),
                ("NumPy", "Prototipo rápido. Validar cerca del umbral epidémico.")],
         n="El problema está limitado por el cómputo (el sorteo aleatorio), no por la memoria: los tableros caben en caché."),

    dict(tipo="tarjetas", k="Cierre", t="Conclusiones",
         cards=[("1", f"El mismo modelo corre en {v('n_paradigmas')} paradigmas con resultados verificados."),
                ("2", f"Speedup máximo ×{v('smax_serial')} vs C++ secuencial y ×{v('smax_numpy')} vs NumPy, con {v('nucleos')} núcleos."),
                ("3", "La referencia importa: NumPy vs C++ mide sobre todo el algoritmo de muestreo."),
                ("4", "Paralelizar bien exigió cuidar los números aleatorios y el estado compartido."),
                ("5", "Medir sin validar no sirve: la versión más rápida fue la menos fiel cerca del umbral.")],
         n="Limitaciones: tableros pequeños, MPI en un solo equipo, CPU y GPU en máquinas distintas, modelo sin control ni tratamiento."),

    dict(tipo="portada", t="Demostración en vivo y preguntas",
         sub="CuPy · C++ con MPI en varios procesos · todas las figuras salen de notebooks/analisis.ipynb",
         n="Comandos de la demo en docs/CHECKLIST_REVISION.md. Repositorio: github.com/dsolartec/hpc-final-project"),
]

QA = [
    ("¿Qué hace el modelo, en una frase?",
     "Simula mes a mes el contagio de malaria entre humanos y mosquitos en una cuadrícula, usando el clima real de cada región de Colombia."),
    ("¿Por qué un modelo de Ross-Macdonald y no un SIR clásico?",
     "Porque la malaria se transmite por un vector: el humano solo se infecta por el mosquito y el mosquito solo por el humano. El SIR clásico supone contagio directo."),
    ("¿Por qué el IPA simulado es tan superior al real?",
     "El modelo no incluye diagnóstico, tratamiento ni control del mosquito: simula transmisión libre. Sirve para estudiar la dinámica, no para pronosticar."),
    ("¿Qué son speedup y eficiencia?",
     "Speedup = tiempo de referencia / tiempo paralelo. Eficiencia = speedup / número de workers; 1 significa aprovechamiento perfecto."),
    ("¿Respecto a qué calculan el speedup?",
     "Dos referencias: C++ secuencial (comparación justa entre paradigmas) y NumPy (ganancia práctica para quien usa Python). En multiprocessing, el mismo lote de réplicas con 1 proceso."),
    ("¿Qué dice la ley de Amdahl y qué fracción paralela obtuvieron?",
     "Que el speedup está limitado por la parte que no se paraleliza: S = 1 / ((1 − f) + f/p). Obtuvimos f = [RESULTADO]."),
    ("¿Diferencia entre Amdahl y Gustafson?",
     "Amdahl fija el tamaño del problema (escalabilidad fuerte); Gustafson lo hace crecer con los procesadores (escalabilidad débil), y por eso predice speedups mayores."),
    ("¿Qué scheduling usaron en OpenMP y por qué?",
     "Partimos de static porque todas las filas tienen el mismo número de celdas (sin costo de planificación, buena localidad). Lo medimos contra dynamic y guided: [RESULTADO]. Si dynamic gana, es porque el costo del sorteo depende del estado de cada celda y la carga por fila no es uniforme."),
    ("¿Cómo evitan las condiciones de carrera?",
     "Con doble tablero: todos leen del tablero actual y cada hilo escribe solo en sus filas del siguiente. No hay bloqueos. Además, cada fila tiene su propio generador aleatorio."),
    ("¿Qué se comunica en MPI y con qué frecuencia?",
     "Solo las filas de borde (6 filas por dirección) con los dos procesos vecinos, antes de cada uno de los 4 sub-pasos del mes, con envío y recepción combinados."),
    ("¿Qué cambiaría en un clúster real?",
     "Los mensajes irían por red, con latencia mucho mayor. Como son mensajes pequeños y frecuentes, la comunicación pesaría más en tableros pequeños; convendría tableros grandes o intercambiar con menos frecuencia."),
    ("¿Por qué en multiprocessing paralelizan réplicas y no el tablero?",
     "El modelo es aleatorio y necesita muchas réplicas; son independientes y no requieren comunicación. Partir el tablero entre procesos de Python costaría más en comunicación que lo que ahorra."),
    ("¿Cómo manejan los números aleatorios en paralelo?",
     "Flujos independientes y semillas documentadas: en C++ un flujo por fila del tablero; en multiprocessing, una semilla distinta por réplica. Nunca se comparte un generador ni se repiten semillas."),
    ("¿Cómo saben que las versiones paralelas son correctas?",
     "Tres niveles: invariantes de conservación, igualdad exacta entre las versiones de C++ y comparación estadística entre lenguajes con varias réplicas."),
    ("¿Qué paradigma recomendarían a un epidemiólogo?",
     "Para estudiar incertidumbre con muchas réplicas, el ensamble con procesos. Para una simulación grande en un solo equipo, OpenMP. MPI o GPU solo cuando el tablero crezca mucho. [RESULTADO: confirmar con datos]"),
]

DEEP = [
    ("¿Por qué una forma de paralelizar es más o menos eficiente?",
     "Depende de cuánto trabajo es independiente y cuánto cuesta coordinar: comunicación (MPI), arranque y copia entre procesos (multiprocessing), estado compartido (OpenMP), transferencias (GPU)."),
    ("¿Cuándo usar una forma y cuándo no?", "Ver la diapositiva «¿Cuándo usar cada técnica?»."),
    ("¿Cómo se comporta la paralelización en CPU?",
     "Escala hasta el número de núcleos físicos; más allá no mejora. Pocos workers «pesados», cada uno con mucho trabajo."),
    ("¿Cómo se comporta en GPU?", "TODO (Daniel): miles de hilos ligeros; rinde con tableros grandes; paga transferencias."),
    ("¿Qué hace diferente a cada herramienta?",
     "NumPy vectoriza en un núcleo; multiprocessing usa procesos sin memoria compartida; OpenMP usa hilos con memoria compartida; MPI usa procesos que se envían mensajes; CuPy/CUDA usan la GPU."),
]




# =============================================================================
# Guion en Markdown
# =============================================================================
def write_md() -> None:
    out = ["# Presentación — guion diapositiva por diapositiva", "",
           "> Generado por `tools/build_presentacion.py` (no editar a mano: edite el script y vuelva a generarlo).",
           "> Sin código en las diapositivas: hallazgos y parámetros. Las cifras salen de las tablas del notebook.",
           f"> Mediciones de CPU: {v('equipo_corto')} ({v('fecha_medicion')}). Duración sugerida: 12–15 minutos.", ""]
    for i, s in enumerate(SLIDES, 1):
        out += [f"## Diapositiva {i} — {s['t']}", ""]
        if s.get("sub"):
            out += [f"*{s['sub']}*", ""]
        if s.get("chips"):
            out += ["**Parámetros:** " + " · ".join(f"{a}: {b}" for a, b in s["chips"]), ""]
        out += [f"- {p}" for p in s.get("p", [])]
        out += [f"- **{a}:** {b}" for a, b in s.get("cards", [])]
        if s.get("kpis"):
            out += ["", "**Cifras destacadas:** " + " · ".join(f"**{a}** {b}" for a, b in s["kpis"])]
        if s.get("f"):
            out += ["", f"**Figura:** `outputs/figures/{s['f']}`"]
        out += ["", f"**Notas del orador:** {s['n']}", ""]
    out += ["---", "", "## Preguntas que debemos dominar (lista de Daniel)", ""]
    out += [f"- **{q}** {a}" for q, a in DEEP]
    out += ["", "## 15 preguntas probables del profesor, con respuestas cortas", ""]
    for i, (q, a) in enumerate(QA, 1):
        out += [f"{i}. **{q}**", f"   {a}", ""]
    (DOCS / "presentacion.md").write_text("\n".join(out), encoding="utf-8")
    print("escrito docs/presentacion.md")


# =============================================================================
# Diapositivas (.pptx)
# =============================================================================
def write_pptx() -> None:
    try:
        from PIL import Image
        from pptx import Presentation
        from pptx.dml.color import RGBColor
        from pptx.enum.shapes import MSO_SHAPE
        from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
        from pptx.util import Inches, Pt
    except ImportError:
        print("python-pptx no está instalado: se omite el .pptx (pip install python-pptx)")
        return

    NAVY, AZUL, CIELO, CORAL = RGBColor(0x0B, 0x25, 0x45), RGBColor(0x13, 0x31, 0x5C), RGBColor(0x98, 0xC1, 0xD9), RGBColor(0xEE, 0x6C, 0x4D)
    FONDO, BLANCO, TINTA, GRIS, BORDE = (RGBColor(0xF5, 0xF7, 0xFB), RGBColor(0xFF, 0xFF, 0xFF), RGBColor(0x1F, 0x29, 0x37),
                                         RGBColor(0x6B, 0x72, 0x80), RGBColor(0xDD, 0xE3, 0xEC))
    HIELO = RGBColor(0xE0, 0xFB, 0xFC)
    FUENTE = "Helvetica Neue"   # en Windows se sustituye por Arial
    W, H = 13.333, 7.5

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(W), Inches(H)
    blank = prs.slide_layouts[6]

    def caja(sl, x, y, w, h, fill, redonda=0.0, linea=None, forma=None):
        shp = sl.shapes.add_shape(forma or (MSO_SHAPE.ROUNDED_RECTANGLE if redonda else MSO_SHAPE.RECTANGLE),
                                  Inches(x), Inches(y), Inches(w), Inches(h))
        if redonda:
            shp.adjustments[0] = redonda
        if fill is None:
            shp.fill.background()
        else:
            shp.fill.solid()
            shp.fill.fore_color.rgb = fill
        if linea is None:
            shp.line.fill.background()
        else:
            shp.line.color.rgb = linea
            shp.line.width = Pt(0.75)
        shp.shadow.inherit = False
        return shp

    def texto(sl, x, y, w, h, t, size, color=TINTA, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, esp=1.0):
        tf = sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)).text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = anchor
        for k, linea in enumerate(t if isinstance(t, list) else [t]):
            par = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
            par.alignment = align
            par.line_spacing = esp
            r = par.add_run()
            r.text = linea
            r.font.size, r.font.bold, r.font.name = Pt(size), bold, FUENTE
            r.font.color.rgb = color
        return tf

    def fondo(sl, color):
        caja(sl, 0, 0, W, H, color)

    def malla(sl, x0, y0, cols, filas, lado=0.34, gap=0.09, semilla=7, oscuro=True):
        rnd = random.Random(semilla)
        base = RGBColor(0x1B, 0x3B, 0x68) if oscuro else RGBColor(0xE4, 0xEA, 0xF3)
        for r in range(filas):
            for c in range(cols):
                col = rnd.choices([base, CORAL, CIELO, AZUL if not oscuro else RGBColor(0x2A, 0x4D, 0x7E)], [62, 9, 11, 18])[0]
                caja(sl, x0 + c * (lado + gap), y0 + r * (lado + gap), lado, lado, col, redonda=0.22)

    def pie(sl, i, oscuro=False):
        c = CIELO if oscuro else GRIS
        texto(sl, 0.6, 7.02, 8, 0.3, "Paralelización de un modelo de malaria  ·  HPC 2026-2  ·  Universidad de Medellín", 9.5, c)
        texto(sl, 11.9, 7.02, 0.85, 0.3, f"{i:02d}", 9.5, c, bold=True, align=PP_ALIGN.RIGHT)

    def cabecera(sl, s, oscuro=False, x=0.6, w=12.1):
        texto(sl, x, 0.42, w, 0.3, s.get("k", "").upper(), 11.5, CORAL, bold=True)
        texto(sl, x, 0.72, w, 0.75, s["t"], 29, BLANCO if oscuro else NAVY, bold=True)
        caja(sl, x, 1.42, 0.85, 0.07, CORAL, redonda=0.5)

    def puntos(sl, x, y, w, items, size=16, color=TINTA, paso=None, marca=CORAL):
        for it in items:
            lineas = max(1, -(-len(it) * size * 0.0088 // (w - 0.27)))  # estimación del número de líneas
            alto = 0.285 * size / 16 * lineas + 0.17
            caja(sl, x, y + 0.085 * size / 16, 0.11, 0.11, marca, redonda=0.3)
            texto(sl, x + 0.27, y - 0.03, w - 0.27, alto, it, size, color, esp=1.08)
            y += paso or alto
        return y

    def kpis(sl, x, y, w, items, oscuro=False, h=1.08):
        n_ = len(items)
        gap = 0.2
        cw = (w - gap * (n_ - 1)) / n_
        for k, (valor, etiqueta) in enumerate(items):
            cx = x + k * (cw + gap)
            caja(sl, cx, y, cw, h, AZUL if oscuro else NAVY, redonda=0.12)
            caja(sl, cx, y, 0.09, h, CORAL)
            tam = 27 if len(valor) <= 6 else (21 if len(valor) <= 9 else 16)
            texto(sl, cx + 0.28, y + 0.1, cw - 0.4, 0.5, valor, tam, BLANCO, bold=True, anchor=MSO_ANCHOR.MIDDLE)
            texto(sl, cx + 0.28, y + 0.58, cw - 0.4, 0.46, etiqueta, 10.5, CIELO, esp=0.95)

    def chips(sl, x, y, w, items, cols=2):
        gap, ch = 0.14, 0.62
        cw = (w - gap * (cols - 1)) / cols
        for k, (clave, valor) in enumerate(items):
            cx, cy = x + (k % cols) * (cw + gap), y + (k // cols) * (ch + gap)
            caja(sl, cx, cy, cw, ch, BLANCO, redonda=0.18, linea=BORDE)
            texto(sl, cx + 0.16, cy + 0.07, cw - 0.3, 0.2, clave.upper(), 8.5, CORAL, bold=True)
            texto(sl, cx + 0.16, cy + 0.27, cw - 0.3, 0.32, valor, 12.5, NAVY, bold=True)
        return y + -(-len(items) // cols) * (ch + gap)

    sin_figura = []

    def figura(sl, nombre, x, y, w, h, oscuro=False):
        caja(sl, x, y, w, h, BLANCO, redonda=0.03, linea=None if oscuro else BORDE)
        ruta = FIG / nombre if nombre else None
        if not ruta or not ruta.exists():
            sin_figura.append(nombre)
            texto(sl, x, y, w, h, ["Figura pendiente", nombre or ""], 13, GRIS, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
            return
        with Image.open(ruta) as im:
            iw, ih = im.size
        m = 0.12
        esc = min((w - 2 * m) / iw, (h - 2 * m) / ih)
        pw, ph = iw * esc, ih * esc
        sl.shapes.add_picture(str(ruta), Inches(x + (w - pw) / 2), Inches(y + (h - ph) / 2), width=Inches(pw), height=Inches(ph))

    for i, s in enumerate(SLIDES, 1):
        sl = prs.slides.add_slide(blank)
        tipo = s["tipo"]

        if tipo == "portada":
            fondo(sl, NAVY)
            caja(sl, 8.4, -2.6, 7.4, 7.4, AZUL, forma=MSO_SHAPE.OVAL)
            caja(sl, 11.2, 4.9, 3.4, 3.4, RGBColor(0x10, 0x2C, 0x52), forma=MSO_SHAPE.OVAL)
            malla(sl, 8.15, 1.55, 11, 8)
            texto(sl, 0.8, 1.25, 7, 0.3, "PROYECTO FINAL  ·  COMPUTACIÓN DE ALTO DESEMPEÑO 2026-2", 12, CIELO, bold=True)
            texto(sl, 0.8, 1.75, 7.0, 2.6, s["t"], 42 if i == 1 else 38, BLANCO, bold=True, esp=0.98)
            caja(sl, 0.8, 4.42, 1.1, 0.085, CORAL, redonda=0.5)
            texto(sl, 0.8, 4.72, 6.9, 1.1, s["sub"], 17, HIELO, esp=1.1)
            texto(sl, 0.8, 6.25, 7.2, 0.3, "Daniel Solarte   ·   Samuel Marroquin   ·   Juan Esteban Ramírez", 13.5, BLANCO, bold=True)
            texto(sl, 0.8, 6.6, 7.2, 0.3, "Universidad de Medellín", 12, CIELO)

        elif tipo == "contexto":
            fondo(sl, FONDO)
            caja(sl, 0, 0, 4.35, H, NAVY)
            malla(sl, 0.55, 5.0, 8, 4, lado=0.3, gap=0.08, semilla=int(s["num"]))
            texto(sl, 0.55, 0.5, 3.4, 1.5, s["num"], 88, CORAL, bold=True)
            texto(sl, 0.58, 2.05, 3.3, 0.3, f"CONTEXTO  ·  {int(s['num'])} DE 4", 11.5, CIELO, bold=True)
            texto(sl, 0.55, 2.42, 3.45, 2.2, s["t"], 31, BLANCO, bold=True, esp=1.0)
            tiene_fig = bool(s.get("f"))
            ancho = 4.1 if tiene_fig else 7.9
            y = puntos(sl, 4.95, 0.78, ancho, s["p"], size=14.5 if tiene_fig else 17.5)
            if tiene_fig:
                figura(sl, s["f"], 9.25, 0.7, 3.65, 4.45)
            if s.get("kpis"):
                kpis(sl, 4.95, 5.55, 7.9, s["kpis"])
            texto(sl, 4.95, 7.02, 7, 0.3, "Paralelización de un modelo de malaria  ·  HPC 2026-2", 9.5, GRIS)
            texto(sl, 11.9, 7.02, 0.85, 0.3, f"{i:02d}", 9.5, GRIS, bold=True, align=PP_ALIGN.RIGHT)

        elif tipo in ("tecnica", "contenido"):
            fondo(sl, FONDO)
            cabecera(sl, s)
            y = 1.78
            if s.get("chips"):
                y = chips(sl, 0.6, y, 5.75, s["chips"]) + 0.12
            puntos(sl, 0.6, y, 5.75, s["p"], size=14 if s.get("chips") else 16)
            figura(sl, s.get("f"), 6.65, 1.72, 6.1, 3.72)
            if s.get("kpis"):
                kpis(sl, 0.6, 5.72, 12.15, s["kpis"])
            pie(sl, i)

        elif tipo == "hallazgo":
            fondo(sl, NAVY)
            caja(sl, 9.6, -2.2, 6.2, 6.2, AZUL, forma=MSO_SHAPE.OVAL)
            cabecera(sl, s, oscuro=True)
            puntos(sl, 0.6, 1.85, 5.7, s["p"], size=15.5, color=HIELO)
            figura(sl, s.get("f"), 6.65, 1.72, 6.1, 3.72, oscuro=True)
            kpis(sl, 0.6, 5.72, 12.15, s["kpis"], oscuro=True)
            pie(sl, i, oscuro=True)

        elif tipo == "figura":
            fondo(sl, FONDO)
            cabecera(sl, s)
            figura(sl, s.get("f"), 0.6, 1.72, 8.05, 5.1)
            y = 1.72
            for valor, etiqueta in s.get("kpis", []):
                caja(sl, 8.9, y, 3.85, 1.12, NAVY, redonda=0.12)
                caja(sl, 8.9, y, 0.09, 1.12, CORAL)
                texto(sl, 9.18, y + 0.1, 3.4, 0.5, valor, 26, BLANCO, bold=True)
                texto(sl, 9.18, y + 0.6, 3.45, 0.5, etiqueta, 10, CIELO, esp=0.95)
                y += 1.27
            puntos(sl, 8.9, y + 0.1, 3.85, s.get("p", []), size=12.5)
            pie(sl, i)

        elif tipo == "tarjetas":
            fondo(sl, FONDO)
            cabecera(sl, s)
            cards = s["cards"]
            arriba = cards[:3]
            abajo = cards[3:]
            for fila_, y0 in ((arriba, 1.85), (abajo, 4.42)):
                n_ = len(fila_)
                if not n_:
                    continue
                cw, gap = 3.85, 0.3
                x0 = 0.6 + (12.15 - (n_ * cw + (n_ - 1) * gap)) / 2
                for k, (cab, cuerpo) in enumerate(fila_):
                    cx = x0 + k * (cw + gap)
                    caja(sl, cx, y0, cw, 2.3, BLANCO, redonda=0.06, linea=BORDE)
                    caja(sl, cx, y0, cw, 0.1, CORAL)
                    numerica = cab.isdigit()
                    texto(sl, cx + 0.28, y0 + 0.3, cw - 0.5, 0.5, cab, 30 if numerica else 19, CORAL if numerica else NAVY, bold=True)
                    texto(sl, cx + 0.28, y0 + (0.95 if numerica else 0.82), cw - 0.5, 1.3, cuerpo, 15, TINTA, esp=1.1)
            pie(sl, i)

        sl.notes_slide.notes_text_frame.text = s["n"]

    prs.save(DOCS / "presentacion.pptx")
    print(f"escrito docs/presentacion.pptx ({len(SLIDES)} diapositivas)")
    faltan = sorted({f for f in sin_figura if f})
    if faltan:
        print("AVISO: figuras no encontradas (se dejó un marcador):", ", ".join(faltan))


if __name__ == "__main__":
    DOCS.mkdir(exist_ok=True)
    write_md()
    write_pptx()
