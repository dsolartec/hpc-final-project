"""
Genera el informe en PDF a partir de docs/informe_plantilla.md.

  1. Rellena los marcadores {{clave}} con los valores medidos (tools/resultados.py lee las
     tablas que produce el notebook) -> docs/informe.md
  2. Convierte a HTML con pandoc y le aplica la hoja de estilo -> docs/informe.html
  3. Imprime a PDF con Chrome/Chromium -> informe.pdf (raíz del repo, guía §6.1)

Uso (desde la raíz del repo, DESPUÉS de ejecutar el notebook):
    python tools/build_informe.py

Requisitos: pandoc y Google Chrome o Chromium.
    macOS:  brew install pandoc        (Chrome instalado en /Applications)
    Linux:  sudo apt install pandoc chromium
Si no hay Chrome, deja docs/informe.html: ábralo en el navegador y use Imprimir > Guardar como PDF.
"""
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "tools"))
from resultados import cargar  # noqa: E402

TITULO = "Paralelización de un autómata celular estocástico para la dinámica de la malaria en Colombia"
SUBTITULO = "Comparación de paradigmas de cómputo en CPU y GPU"
AUTORES = "Daniel Solarte · Samuel Marroquin · Juan Esteban Ramírez"
CURSO = "Computación de Alto Desempeño (HPC) 2026-2 · Universidad de Medellín"

CSS = r"""
@page { size: A4; margin: 22mm 19mm 20mm 19mm;
        @bottom-center { content: counter(page); font-family: Inter, 'Helvetica Neue', Arial, sans-serif; font-size: 8.5pt; color: #6b7280; }
        @top-right { content: "Paralelización de un modelo de malaria — HPC 2026-2"; font-family: Inter, 'Helvetica Neue', Arial, sans-serif; font-size: 7.5pt; color: #9ca3af; } }
@page :first { margin: 0; @bottom-center { content: none; } @top-right { content: none; } }
* { box-sizing: border-box; }
html { font-size: 10.2pt; }
body { font-family: Inter, 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #1f2937; line-height: 1.5; margin: 0;
       -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.portada { height: 297mm; width: 210mm; background: linear-gradient(150deg, #0b2545 0%, #13315c 55%, #134074 100%); color: #fff;
           padding: 38mm 24mm 24mm 24mm; display: flex; flex-direction: column; page-break-after: always; position: relative; overflow: hidden; }
.portada::before { content: ""; position: absolute; right: -60mm; top: -40mm; width: 190mm; height: 190mm; border-radius: 50%;
                   background: radial-gradient(circle, rgba(238,108,77,.35) 0%, rgba(238,108,77,0) 68%); }
.portada .malla { position: absolute; right: 18mm; bottom: 62mm; display: grid; grid-template-columns: repeat(12, 7mm); gap: 1.6mm; opacity: .9; }
.portada .malla i { width: 7mm; height: 7mm; border-radius: 1.4mm; background: rgba(255,255,255,.07); }
.portada .malla i.a { background: #ee6c4d; } .portada .malla i.b { background: #98c1d9; } .portada .malla i.c { background: rgba(255,255,255,.22); }
.portada .etiqueta { font-size: 9.5pt; letter-spacing: .22em; text-transform: uppercase; color: #98c1d9; font-weight: 600; }
.portada h1 { font-size: 27pt; line-height: 1.16; font-weight: 800; margin: 9mm 0 5mm 0; max-width: 150mm; border: 0; color: #fff; letter-spacing: -.01em; }
.portada .sub { font-size: 13.5pt; color: #e0fbfc; font-weight: 400; max-width: 140mm; }
.portada .barra { width: 26mm; height: 1.6mm; background: #ee6c4d; border-radius: 1mm; margin: 9mm 0; }
.portada .pie { margin-top: auto; font-size: 10.5pt; line-height: 1.7; position: relative; }
.portada .pie b { font-weight: 600; } .portada .pie span { color: #98c1d9; }
main { padding: 0; }
h2 { font-size: 15.5pt; color: #0b2545; margin: 9mm 0 3mm; padding-bottom: 1.6mm; border-bottom: .7mm solid #ee6c4d; font-weight: 800;
     letter-spacing: -.01em; page-break-after: avoid; }
h3 { font-size: 11.8pt; color: #13315c; margin: 6mm 0 2mm; font-weight: 700; page-break-after: avoid; }
p { margin: 0 0 2.6mm; text-align: justify; hyphens: auto; }
ul, ol { margin: 0 0 3mm; padding-left: 6mm; } li { margin-bottom: 1.1mm; text-align: justify; }
code { font-family: 'JetBrains Mono', 'SF Mono', Menlo, Consolas, 'DejaVu Sans Mono', monospace; font-size: 8.6pt; background: #eef2f7;
       padding: .2mm 1mm; border-radius: 1mm; color: #13315c; }
strong { color: #111827; }
hr { display: none; }
table { border-collapse: collapse; width: 100%; margin: 2.5mm 0 5mm; font-size: 8.6pt; page-break-inside: avoid; }
thead th { background: #0b2545; color: #fff; font-weight: 600; padding: 1.8mm 2.2mm; text-align: left; border: 0; }
tbody td { padding: 1.5mm 2.2mm; border-bottom: .2mm solid #e5e7eb; vertical-align: top; }
tbody tr:nth-child(even) td { background: #f6f8fb; }
figure { margin: 4mm 0 5mm; text-align: center; page-break-inside: avoid; }
figure img { max-width: 100%; max-height: 118mm; border: .25mm solid #e5e7eb; border-radius: 1.5mm; padding: 1.5mm; background: #fff; }
figcaption { font-size: 8.4pt; color: #4b5563; margin-top: 1.6mm; text-align: center; padding: 0 6mm; line-height: 1.4; }
blockquote { margin: 3mm 0; padding: 2.5mm 4mm; background: #fff7ed; border-left: 1.1mm solid #ee6c4d; border-radius: 1mm; font-size: 9.2pt; }
blockquote p { margin: 0; }
.resumen { background: #f1f5f9; border-radius: 2mm; padding: 5mm 6mm; margin-bottom: 5mm; }
.resumen p { margin-bottom: 2mm; }
.pend { background: #fff3c4; color: #7a4b00; border: .2mm solid #f2c94c; border-radius: 1mm; padding: 0 1.2mm; font-size: 8.6pt; font-weight: 600; }
.aviso { background: #fff7ed; border: .25mm solid #fdba74; border-radius: 2mm; padding: 3mm 4.5mm; font-size: 9pt; margin: 0 0 6mm; }
.refs p { text-align: left; padding-left: 7mm; text-indent: -7mm; font-size: 9pt; margin-bottom: 1.8mm; }
"""


def portada() -> str:
    import random
    rnd = random.Random(7)
    celdas = "".join(f'<i class="{rnd.choices(["", "a", "b", "c"], [62, 9, 11, 18])[0]}"></i>' for _ in range(12 * 9))
    return f"""<section class="portada">
  <div class="etiqueta">Proyecto final · Informe técnico</div>
  <h1>{TITULO}</h1>
  <div class="sub">{SUBTITULO}</div>
  <div class="barra"></div>
  <div class="malla">{celdas}</div>
  <div class="pie"><b>{AUTORES}</b><br><span>{CURSO}</span><br><span>github.com/dsolartec/hpc-final-project</span></div>
</section>"""


def rellenar(texto: str, R: dict) -> tuple[str, list[str]]:
    faltan = []

    def sub(m):
        k = m.group(1)
        if k in R:
            return str(R[k])
        faltan.append(k)
        return f"[PENDIENTE: {k}]"
    return re.sub(r"\{\{(\w+)\}\}", sub, texto), faltan


def buscar_chrome() -> str | None:
    candidatos = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ] + [shutil.which(n) or "" for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")]
    candidatos += [str(p) for p in Path("/opt/pw-browsers").glob("chromium-*/chrome-linux*/chrome")]
    return next((c for c in candidatos if c and Path(c).exists()), None)


def main() -> int:
    R = cargar()
    if R.get("_faltan_tablas"):
        print("ERROR: faltan las tablas de outputs/figures/. Ejecute primero el notebook:\n"
              "  python -m jupyter execute --inplace notebooks/analisis.ipynb")
        return 1
    md, faltan = rellenar((DOCS / "informe_plantilla.md").read_text(encoding="utf-8"), R)
    # Las figuras que no existan (p. ej. GPU) se sustituyen por una nota, para no dejar imágenes rotas.
    def fig(m):
        ruta = (DOCS / m.group(2)).resolve()
        return m.group(0) if ruta.exists() else f"[PENDIENTE: figura {ruta.name} — ejecutar el notebook]"
    md = re.sub(r"!\[(.*?)\]\((\.\./outputs/figures/[^)]+)\)", fig, md)
    (DOCS / "informe.md").write_text(
        "<!-- Generado por tools/build_informe.py a partir de docs/informe_plantilla.md. No editar a mano. -->\n\n"
        f"# {TITULO}\n\n**{AUTORES}** — {CURSO}\n\n" + md, encoding="utf-8")
    print(f"escrito docs/informe.md ({len(md.split())} palabras)")
    if faltan:
        print("AVISO: marcadores sin valor:", ", ".join(sorted(set(faltan))))

    if not shutil.which("pandoc"):
        print("AVISO: pandoc no está instalado; no se genera el PDF (brew install pandoc / apt install pandoc).")
        return 0
    cuerpo = subprocess.run(
        ["pandoc", "--from", "markdown+pipe_tables+implicit_figures-smart", "--to", "html5", "--wrap=none"],
        input=md, capture_output=True, text=True, check=True).stdout
    # Estilo de los pendientes, del resumen y de las referencias
    cuerpo = re.sub(r"\[(PENDIENTE|TODO \(Daniel\)|REFERENCIA POR VERIFICAR)([^\]]*)\]", r'<span class="pend">\1\2</span>', cuerpo)
    cuerpo = re.sub(r"(?<![\w>])TODO \(Daniel\)(:?)", r'<span class="pend">TODO (Daniel)\1</span>', cuerpo)
    cuerpo = re.sub(r'(<h2 id="resumen">.*?</h2>)(.*?)(<h2)', r'\1<div class="resumen">\2</div>\3', cuerpo, count=1, flags=re.S)
    cuerpo = re.sub(r'(<h2 id="referencias">.*?</h2>)(.*)$', r'\1<div class="refs">\2</div>', cuerpo, count=1, flags=re.S)
    n_pend = cuerpo.count('class="pend"')
    aviso = (f'<div class="aviso"><b>Versión de trabajo.</b> Mediciones de CPU del {R["fecha_medicion"]} en: {R["equipo_corto"]}. '
             f'Quedan {n_pend} marcas amarillas por completar (GPU, horas de trabajo, perfilador y referencias por verificar). '
             'Este PDF se regenera con <code>python tools/build_informe.py</code> después de ejecutar el notebook.</div>') if n_pend else ""
    html = (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{TITULO}</title><style>{CSS}</style></head>'
            f"<body>{portada()}<main>{aviso}{cuerpo}</main></body></html>")
    salida_html = DOCS / "informe.html"
    salida_html.write_text(html, encoding="utf-8")
    print("escrito docs/informe.html")

    chrome = buscar_chrome()
    if not chrome:
        print("AVISO: no se encontró Chrome/Chromium. Abra docs/informe.html y use Imprimir > Guardar como PDF "
              "(márgenes: predeterminados; activar 'Gráficos de fondo').")
        return 0
    pdf = ROOT / "informe.pdf"
    subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", salida_html.as_uri()], capture_output=True, text=True, timeout=180)
    if pdf.exists():
        print(f"escrito informe.pdf ({pdf.stat().st_size / 1e6:.1f} MB; {n_pend} pendientes marcados)")
    else:
        print("AVISO: Chrome no generó el PDF; abra docs/informe.html e imprímalo a PDF.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
