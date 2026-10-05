"""Build slides/redshift-redemption.pptx from the community template.

Structure (slide copies) is made with the pptx skill's add_slide.py/clean.py,
then python-pptx fills each slide. Numbers are read from results/, never typed.
Wording lives here; slides/contenido.md is generated from the built deck.

Usage: python slides/build_deck.py <pptx-skill-dir>
Needs: python-pptx, defusedxml, lxml (any venv).
"""
import csv
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "slides/evento/plantilla-oct-epII.pptx"
OUT = ROOT / "slides/redshift-redemption.pptx"
R = ROOT / "results/2026-10-05"
sys.path.insert(0, str(ROOT / "runner"))
from rr import stats  # noqa: E402
from rr.results import read_rows  # noqa: E402

WHITE, ACCENT, ORANGE = RGBColor(0xFF, 0xFF, 0xFF), RGBColor(0x31, 0x6C, 0xE3), RGBColor(0xF2, 0xA6, 0x5A)
SOFT, MUTED, CARD = RGBColor(0xD9, 0xE2, 0xEC), RGBColor(0x9F, 0xB3, 0xC8), RGBColor(0x2F, 0x3D, 0x52)
CODEBG, RA3C = RGBColor(0x1A, 0x22, 0x30), RGBColor(0x8F, 0xA3, 0xB8)
BODY = "Arial"
X0, Y0, W0, H0 = 1.0, 3.5, 15.9, 6.0  # inside the template's rounded panel (inches)

# template slide per deck slide: 2 agenda, 4/6/8 title+content, 10/12/14 transition (dark variants)
SRC = [4, 4, 2, 4, 10, 6, 6, 6, 12, 8, 8, 8, 14, 4, 4, 4, 4, 4, 4, 10, 6, 6, 6, 6, 6, 12, 8, 8, 14, 4, 4, 4, 6, 6, 6, 6, 6]


# Quiz: at least 3 questions about the talk; Kahoot: 2 simpler ones (organizers' email, 2026-10-05).
QUIZ = [
    {"q": "¿Con qué lee RG los datos del data lake?",
     "opts": ["Redshift Spectrum", "Con sus propios nodos, sin Spectrum", "Amazon Athena", "Trabajos de AWS Glue"], "ok": 1,
     "why": "RA3 usa Spectrum, que cobra USD 5 por TB leído; RG lee el data lake con sus propios nodos y sin ese cobro."},
    {"q": "¿Qué tipo de consultas mejoró más al pasar de RA3 a RG?",
     "opts": ["Las de cálculo pesado (ventanas, joins grandes)", "Ninguna, quedaron igual", "Las que leen y agregan muchos datos", "Solo las del data lake"], "ok": 2,
     "why": "2,28 veces en lectura contra 1,58 en cálculo; el promedio de las 20 consultas fue 1,90."},
    {"q": "Si tienes 4 nodos ra3.4xlarge, ¿cuántos rg.4xlarge recomienda AWS?",
     "opts": ["3", "4", "2", "8"], "ok": 0,
     "why": "Un ra3.4xlarge tiene 12 vCPU y un rg.4xlarge, 16: 4 × 12 = 3 × 16 = 48. Migrar uno a uno en ese tamaño deja un tercio de capacidad de más."},
    {"q": "En el simulacro de migración (elastic resize), ¿cuánto tiempo estuvo el clúster sin aceptar escrituras?",
     "opts": ["Nada, siempre aceptó escrituras", "Unos 30 minutos", "Varias horas", "Entre 1,5 y 3 minutos"], "ok": 3,
     "why": "Entre 1 min 35 s y 2 min 42 s; el resize completo tomó 2 min 48 s."},
]
KAHOOT = [
    {"q": "¿Qué procesadores usan los nuevos nodos RG de Redshift?",
     "opts": ["Intel Xeon", "AMD EPYC", "AWS Graviton", "Apple M"], "ok": 2,
     "why": "RG usa Graviton, los procesadores Arm diseñados por AWS."},
    {"q": "¿Cuánto menos cuesta RG por vCPU frente a RA3?",
     "opts": ["30 %", "10 %", "50 %", "Cuesta lo mismo"], "ok": 0,
     "why": "USD 1,086 entre 4 vCPU en ra3.xlplus contra 0,7602 entre 4 en rg.xlarge: 30 % menos."},
]

# ---------------------------------------------------------------- data
def power_rows():
    rows = []
    for line in (R / "summary-power.md").read_text().splitlines():
        m = re.match(r"\| (query\d+) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+)x \|", line)
        if m:
            rows.append((m[1], float(m[2]), float(m[3]), float(m[4])))
    return rows


def power_summary():
    t = (R / "summary-power.md").read_text()
    g = lambda pat: re.search(pat, t)[1]
    return {"geo": g(r"geométrica\): ([\d.]+)x"), "scan": g(r"\| scan \| ([\d.]+)x"), "cpu": g(r"\| cpu \| ([\d.]+)x"),
            "tot": re.search(r"total \(s\) \| ([\d.]+) \| ([\d.]+)", t).groups(),
            "p50": re.search(r"p50 / p95 \(s\) \| ([\d.]+) /[^|]*\| ([\d.]+) /", t).groups(),
            "usd": re.search(r"USD por corrida \| ([\d.]+) \| ([\d.]+)", t).groups()}


def classes():
    out = {}
    for line in (ROOT / "sql/curated.txt").read_text().splitlines():
        if line and not line.startswith("#"):
            name, cls = line.split()[:2]
            out[name] = cls
    return out


def per_q(run):
    return stats.per_query(read_rows(str(R / f"{run}-timings.csv")))


def tot(run):
    return sum(per_q(run).values())


def qph(run):
    return stats.throughput(read_rows(str(R / f"{run}-timings.csv")), 1800)["queries_per_hour"]


def es(x, nd=1):  # Spanish decimal comma
    return f"{x:.{nd}f}".replace(".", ",")


# ---------------------------------------------------------------- shape helpers
def _runs(p, text, size, color, bold_all=False, font=BODY):
    parts = re.split(r"(\*\*[^*]+\*\*)", text)
    for part in parts:
        if not part:
            continue
        r = p.add_run()
        b = part.startswith("**")
        r.text = part.strip("*") if b else part
        f = r.font
        f.size, f.name, f.bold = Pt(size), font, bold_all or b
        f.color.rgb = color


def textbox(slide, x, y, w, h, paras, size=24, color=SOFT, bullets=False, align=PP_ALIGN.LEFT,
            anchor=MSO_ANCHOR.TOP, font=BODY, space=10, bold=False, name=None):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap, tf.vertical_anchor = True, anchor
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, m, 0)
    for i, text in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment, p.space_after = align, Pt(space)
        if bullets:
            pPr = p._p.get_or_add_pPr()
            pPr.set("marL", str(Inches(0.38))), pPr.set("indent", str(-Inches(0.38)))
            bu = etree.SubElement(pPr, "{http://schemas.openxmlformats.org/drawingml/2006/main}buChar")
            bu.set("char", "•")
        _runs(p, text, size, color, bold, font)
    return tb


def card(slide, x, y, w, h, title, body, size=22, title_color=WHITE, fill=CARD, title_size=None):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.adjustments[0] = 0.08
    s.fill.solid(), setattr(s.fill.fore_color, "rgb", fill)
    s.line.fill.background()
    s.shadow.inherit = False
    tf = s.text_frame
    tf.word_wrap, tf.vertical_anchor = True, MSO_ANCHOR.TOP
    for m in ("margin_left", "margin_right"):
        setattr(tf, m, Inches(0.3))
    tf.margin_top = tf.margin_bottom = Inches(0.25)
    p = tf.paragraphs[0]
    p.space_after = Pt(8)
    _runs(p, title, title_size or size + 4, title_color, True)
    for line in ([body] if isinstance(body, str) else body):
        q = tf.add_paragraph()
        q.space_after = Pt(6)
        _runs(q, line, size, SOFT)
    return s


def stat(slide, x, y, w, big, label, color=ACCENT, size=80, label_size=22):
    textbox(slide, x, y, w, 1.4, [big], size=size, color=color, bold=True, anchor=MSO_ANCHOR.BOTTOM)
    textbox(slide, x, y + 1.5, w, 1.2, [label], size=label_size, color=SOFT)


def code(slide, x, y, w, h, text, size=17):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.adjustments[0] = 0.04
    s.fill.solid(), setattr(s.fill.fore_color, "rgb", CODEBG)
    s.line.fill.background()
    tf = s.text_frame
    tf.word_wrap, tf.vertical_anchor = True, MSO_ANCHOR.TOP
    tf.margin_left = tf.margin_right = tf.margin_top = Inches(0.3)
    for i, line in enumerate(text.splitlines()):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        r = p.add_run()
        r.text = line
        r.font.name, r.font.size, r.font.color.rgb = "Courier New", Pt(size), SOFT


def table(slide, x, y, w, rows, col_w, size=20, row_h=0.62, hl_rows=()):
    shp = slide.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(row_h * len(rows)))
    t = shp.table
    for j, cw in enumerate(col_w):
        t.columns[j].width = Inches(cw)
    for i, row in enumerate(rows):
        t.rows[i].height = Inches(row_h)
        for j, val in enumerate(row):
            c = t.cell(i, j)
            c.fill.solid()
            c.fill.fore_color.rgb = ACCENT if i == 0 else (RGBColor(0x3A, 0x4B, 0x66) if i in hl_rows else CARD)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.margin_left = c.margin_right = Inches(0.12)
            p = c.text_frame.paragraphs[0]
            p.text = ""
            _runs(p, str(val), size, WHITE, i == 0)
    return shp


def bar_chart(slide, x, y, w, h, cats, series, colors, horizontal=False, fmt='0.0', point_colors=None,
              label_size=16, axis_size=16, legend=False, gap=60, label_fn=None):
    data = CategoryChartData()
    data.categories = cats
    for name, vals in series:
        data.add_series(name, vals)
    kind = XL_CHART_TYPE.BAR_CLUSTERED if horizontal else XL_CHART_TYPE.COLUMN_CLUSTERED
    gf = slide.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), data)
    ch = gf.chart
    ch.has_title = False
    ch.has_legend = legend
    if legend:
        ch.legend.include_in_layout = False
        from pptx.enum.chart import XL_LEGEND_POSITION
        ch.legend.position = XL_LEGEND_POSITION.BOTTOM
        ch.legend.font.size, ch.legend.font.color.rgb, ch.legend.font.name = Pt(axis_size), SOFT, BODY
    ch.font.name, ch.font.size, ch.font.color.rgb = BODY, Pt(axis_size), SOFT
    plot = ch.plots[0]
    plot.gap_width = gap
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format, dl.number_format_is_linked = fmt, False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size, dl.font.color.rgb, dl.font.name = Pt(label_size), WHITE, BODY
    for s, col in zip(plot.series, colors):
        s.format.fill.solid(), setattr(s.format.fill.fore_color, "rgb", col)
    if point_colors:
        for i, col in enumerate(point_colors):
            pt = plot.series[0].points[i]
            pt.format.fill.solid(), setattr(pt.format.fill.fore_color, "rgb", col)
    va, ca = ch.value_axis, ch.category_axis
    va.has_major_gridlines = False
    va.visible = False
    ca.tick_labels.font.size, ca.tick_labels.font.color.rgb = Pt(axis_size), SOFT
    ca.format.line.color.rgb = MUTED
    if horizontal:
        ca.reverse_order = True
    if label_fn:  # number formats follow the viewer's locale; write the Spanish label as text
        for (name, vals), ser in zip(series, plot.series):
            for i, v in enumerate(vals):
                tf = ser.points[i].data_label.text_frame
                tf.text = label_fn(v)
                r = tf.paragraphs[0].runs[0]
                r.font.size, r.font.color.rgb, r.font.name = Pt(label_size), WHITE, BODY
                ser.points[i].data_label.position = XL_LABEL_POSITION.OUTSIDE_END
    return ch


def picture(slide, path, x, y, w, h):
    from PIL import Image
    iw, ih = Image.open(path).size
    scale = min(w / iw, h / ih)
    pw, ph = iw * scale, ih * scale
    return slide.shapes.add_picture(str(path), Inches(x + (w - pw) / 2), Inches(y + (h - ph) / 2), Inches(pw), Inches(ph))


HEAD = "Arial Black"  # the template's embedded "Raleway 1 Heavy" garbles letters in PowerPoint for Mac


def _heavy(run, size=None):
    """Heading font on every script slot (latin/ea/cs/sym), no synthetic bold."""
    rPr = run._r.get_or_add_rPr()
    rPr.set("b", "0")
    if size:
        rPr.set("sz", str(int(size * 100)))
    A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    for tag in ("latin", "ea", "cs", "sym"):
        el = rPr.find(A + tag)
        if el is None:
            el = etree.SubElement(rPr, A + tag)
        el.set("typeface", HEAD)


def qr(slide, path, x, y, size, caption):
    pad = 0.18
    bg = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x - pad), Inches(y - pad), Inches(size + 2 * pad), Inches(size + 2 * pad))
    bg.adjustments[0] = 0.06
    bg.fill.solid(), setattr(bg.fill.fore_color, "rgb", WHITE)
    bg.line.fill.background()
    slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(size), Inches(size))
    textbox(slide, x - 0.5, y + size + 0.3, size + 1.0, 0.5, [caption], size=18, color=SOFT, align=PP_ALIGN.CENTER)


def set_title(slide, text, size=54):
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip() in ("TÍTULO",):
            sh.left, sh.top, sh.width, sh.height = Inches(3.85), Inches(0.95), Inches(13.2), Inches(2.05)
            size = min(size, int(13.0 * 72 / (0.68 * len(text))))  # Arial Black is wide: fit one line
            tf = sh.text_frame
            tf.word_wrap, tf.vertical_anchor = True, MSO_ANCHOR.MIDDLE
            run = tf.paragraphs[0].runs[0]
            run.text = text
            _heavy(run, size)
            for extra in tf.paragraphs[0].runs[1:]:
                extra.text = ""
            return
    raise ValueError("no TÍTULO box")


def set_transition(slide, line1, line2=""):
    for sh in slide.shapes:
        if sh.has_text_frame and "TRANSICI" in sh.text_frame.text:
            p1, p2 = sh.text_frame.paragraphs[:2]
            p1.runs[0].text = line1
            _heavy(p1.runs[0], 88)
            for r in p1.runs[1:]:
                r.text = ""
            p2.runs[0].text = ("        " + line2) if line2 else ""
            _heavy(p2.runs[0], 88)
            for r in p2.runs[1:]:
                r.text = ""
            return
    raise ValueError("no transition box")


def set_agenda(slide, items):
    for sh in slide.shapes:
        if sh.has_text_frame and "primer tema" in sh.text_frame.text:
            for p, item in zip(sh.text_frame.paragraphs, items):
                p.runs[0].text = item
                for r in p.runs[1:]:
                    r.text = ""
            return
    raise ValueError("no agenda box")


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = " ".join(text.split())


# ---------------------------------------------------------------- structure
def build_structure(skill: Path, tmp: Path) -> Path:
    unpacked = tmp / "u"
    zipfile.ZipFile(TEMPLATE).extractall(unpacked)
    created = []
    for src in SRC:
        out = subprocess.run([sys.executable, str(skill / "scripts/add_slide.py"), str(unpacked), f"slide{src}.xml"],
                             check=True, capture_output=True, text=True).stdout
        created.append(re.search(r"(slide\d+\.xml)", out.split("Created")[-1])[1])
    pres = unpacked / "ppt/presentation.xml"
    rels = (unpacked / "ppt/_rels/presentation.xml.rels").read_text()
    rid = {m[2]: m[1] for m in re.finditer(r'Id="(rId\d+)"[^>]*Target="slides/(slide\d+\.xml)"', rels)}
    rid.update({m[1]: m[0] for m in re.finditer(r'Target="slides/(slide\d+\.xml)"[^>]*Id="(rId\d+)"', rels)} and {})
    xml = pres.read_text()
    ids = re.findall(r'<p:sldId [^>]*/>', xml)
    by_rid = {re.search(r'r:id="(rId\d+)"', e)[1]: e for e in ids}
    keep = [by_rid[rid[f]] for f in created]
    xml = re.sub(r"<p:sldIdLst>.*?</p:sldIdLst>", "<p:sldIdLst>" + "".join(keep) + "</p:sldIdLst>", xml, flags=re.S)
    pres.write_text(xml)
    subprocess.run([sys.executable, str(skill / "scripts/clean.py"), str(unpacked)], check=True, capture_output=True)
    out = tmp / "structure.pptx"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(unpacked.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(unpacked))
    return out


# ---------------------------------------------------------------- content
def pair_stat(slide, x, y, w, label, a, b, unit="s", nd=1, note="menos tiempo es mejor"):
    """RA3 vs RG side by side with what the numbers mean."""
    textbox(slide, x, y, w, 0.5, [label], size=20, color=SOFT)
    textbox(slide, x, y + 0.55, w / 2, 1.0, [f"{es(a, nd)} {unit}"], size=40, color=RA3C, bold=True)
    textbox(slide, x + w / 2, y + 0.55, w / 2, 1.0, [f"{es(b, nd)} {unit}"], size=40, color=ACCENT, bold=True)
    textbox(slide, x, y + 1.4, w / 2, 0.5, ["RA3"], size=18, color=RA3C)
    textbox(slide, x + w / 2, y + 1.4, w / 2, 0.5, ["RG"], size=18, color=ACCENT)
    if note:
        textbox(slide, x, y + 1.85, w, 0.5, [note], size=16, color=MUTED)


def fill(prs):
    S = prs.slides
    ps, pr, cls = power_summary(), power_rows(), classes()
    ra3_q, rg_q = qph("rr-ra3-concurrency-8c56"), qph("rr-rg-concurrency-8599")
    elt_a, elt_g = per_q("rr-ra3-elt-b9f7"), per_q("rr-rg-elt-0a03")
    ice_a, ice_g = per_q("rr-ra3-lake-glue-e691"), per_q("rr-rg-lake-glue-9d55")
    pq_runs = [("rr-ra3-lake-parquet-68e7", "rr-rg-lake-parquet-dd2f"), ("rr-ra3-lake-parquet-df42", "rr-rg-lake-parquet-f7c8")]
    pq1, pq2 = [(tot(a), tot(g), stats.geomean(stats.speedups(per_q(a), per_q(g)).values())) for a, g in pq_runs]
    q96 = next(r for r in pr if r[0] == "query96")
    geo = es(float(ps["geo"]), 2)

    # 1 cover
    s = S[0]
    set_title(s, "Redshift Redemption", 72)
    textbox(s, X0, Y0 + 0.4, 9.6, 4.5, ["Los nuevos nodos RG: **¿migrar o no migrar?**",
                                         "Andrés Zeballos · Solutions Architect en phData",
                                         "Medido con 100 GB de TPC-DS · octubre de 2026"], size=30, space=22)
    stat(s, 11.4, Y0 + 0.5, 5.4, f"{geo}x", "más rápido, en promedio, en nuestras pruebas", size=110)
    notes(s, "Buenas tardes. Hoy no vengo a repetir el anuncio de AWS: vengo a contarles qué pasó cuando lo puse a prueba. Ese 1,90 es uno de los resultados, y al final van a ver que no es el único que importa.")

    # 2 bio
    s = S[1]
    set_title(s, "Quién soy")
    textbox(s, X0, Y0 + 0.1, 9.9, 5.6, [
        "Soy de Arequipa y trabajo como Solutions Architect en phData, casi siempre con AWS.",
        "Empecé en redes y fui pasando por infraestructura, Kubernetes y datos. Hoy ando metido con agentes de IA.",
        "Tengo el Golden Jacket de AWS y hace poco me invitaron a ayudar a crear las nuevas microcredenciales de análisis de datos."],
        size=25, space=20)
    card(s, 11.4, Y0 + 0.2, 5.0, 3.6, "Probar antes de recomendar",
         "Cada charla que doy sale de un laboratorio que armo y después publico para que cualquiera lo repita.",
         size=21, title_size=28, title_color=ACCENT)
    notes(s, "Me gusta probar las cosas antes de recomendarlas. Esta charla es justamente eso: un laboratorio que armé esta semana, con lo que costó y con los errores que me encontré en el camino.")

    # 3 agenda
    set_agenda(S[2], ["Qué cambia con RG", "Cómo lo medimos", "Warehouse: velocidad, concurrencia y costo",
                      "Data lake: Iceberg, Parquet y Spectrum", "La migración y lo que nadie te cuenta", "Demo"])
    notes(S[2], "Cinco temas y una demo. Al final les doy una respuesta concreta a la pregunta del título, y cerramos con tres preguntas de Kahoot.")

    # 4 question
    s = S[3]
    set_title(s, "¿Migro o no migro?")
    card(s, X0, Y0, 4.6, 2.6, "RA3", "Lo que usas hoy", size=24, title_size=54, title_color=RA3C)
    textbox(s, X0 + 4.6, Y0 + 0.5, 1.4, 1.6, ["?"], size=88, color=ORANGE, bold=True, align=PP_ALIGN.CENTER)
    card(s, X0 + 6.0, Y0, 4.6, 2.6, "RG", "Con Graviton, desde mayo de 2026", size=24, title_size=54, title_color=ACCENT)
    textbox(s, X0, Y0 + 3.1, 15.2, 2.8, ["Si tienes un Redshift con nodos RA3, o eres quien paga la factura, seguramente ya te hiciste esta pregunta.",
                                          "Hoy revisamos lo que anunció AWS con pruebas propias: **en qué se cumple y en qué depende de cómo usas Redshift.**"],
            size=26, space=16)
    notes(s, "La idea no es desmentir a nadie. AWS publicó sus números y yo los revisé en un clúster chico, como el que tienen muchos equipos. Donde se cumplen, lo digo; donde dependen de algo, les explico de qué.")

    # 5 transition
    set_transition(S[4], "QUÉ", "CAMBIA")
    notes(S[4], "Primero, qué es exactamente un nodo RG y en qué se diferencia de RA3.")

    # 6 what's new
    s = S[5]
    set_title(s, "Qué trae RG")
    cards = [("Procesadores Graviton", "Los chips Arm diseñados por AWS"),
             ("El data lake sin Spectrum", "RG consulta los datos en S3 con sus propios nodos; RA3 depende de Spectrum, un servicio aparte"),
             ("Sin cobro por TB leído", "En RA3, Spectrum cobra USD 5 por cada TB que lee; en RG ese cobro no existe"),
             ("Lo que se mantiene", "El mismo Redshift de siempre y el mismo almacenamiento administrado (USD 0,024 por GB al mes)")]
    for i, (t, b) in enumerate(cards):
        card(s, X0 + (i % 2) * 7.85, Y0 + (i // 2) * 2.95, 7.55, 2.65, t, b, size=22,
             title_color=ACCENT if i < 3 else RA3C)
    notes(s, "Esto es clave para entender los resultados del data lake: cuando comparamos RA3 con RG ahí, no comparamos solo procesadores, comparamos dos formas distintas de leer S3. Por eso hablo del chip y de cómo se leen los datos, nunca del chip solo. Fuente: documentación de Redshift, Amazon Redshift provisioned clusters.")

    # 7 sizes and prices
    s = S[6]
    set_title(s, "Cuatro tamaños y 30 % menos por vCPU", 50)
    rows = [["RA3", "vCPU", "USD/hora", "", "RG", "vCPU", "USD/hora", "USD por vCPU y hora"],
            ["—", "", "", "", "rg.large", "2", "0,3801", "0,190"],
            ["ra3.xlplus", "4", "1,086", "1 : 1", "rg.xlarge", "4", "0,7602", "de 0,272 a 0,190"],
            ["ra3.4xlarge", "12", "3,26", "4 : 3", "rg.4xlarge", "16", "3,04267", "de 0,272 a 0,190"],
            ["—", "", "", "", "rg.12xlarge", "48", "9,128", "0,190"]]
    table(s, X0, Y0, 15.2, rows, [2.4, 1.1, 1.75, 0.9, 2.5, 1.1, 1.75, 3.7], size=21, row_h=0.72, hl_rows=(3,))
    textbox(s, X0, Y0 + 4.0, 15.2, 1.6, ["**4 nodos ra3.4xlarge equivalen a 3 rg.4xlarge** (48 vCPU en total): USD 13,04 frente a 9,13 por hora"],
            size=26, color=WHITE)
    textbox(s, X0, Y0 + 5.15, 15.2, 0.6, ["vCPU: documentación de Redshift («Node type details»). Precios on-demand en us-east-1, Price List API."],
            size=16, color=MUTED)
    notes(s, "El 30 % por vCPU se cumple al centavo: 1,086 dividido entre 4 vCPU contra 0,7602 entre 4. Ojo con el tamaño 4xlarge: un ra3.4xlarge tiene 12 vCPU y un rg.4xlarge tiene 16, por eso AWS recomienda pasar de 4 nodos a 3. Si migras uno a uno en ese tamaño, terminas pagando un tercio más de capacidad de la que tenías.")

    # 8 AWS's announcement
    s = S[7]
    set_title(s, "Lo que anunció AWS")
    proms = [("Hasta 2,2x", "más rápido en las consultas del warehouse"), ("Hasta 2,4x", "en el data lake con Iceberg (1,5x con Parquet)"),
             ("−30 %", "en el precio por vCPU"), ("USD 0", "por TB leído desde el data lake")]
    for i, (t, b) in enumerate(proms):
        card(s, X0 + i * 3.88, Y0, 3.65, 3.0, t, b, size=22, title_size=40, title_color=ACCENT)
    textbox(s, X0, Y0 + 3.5, 15.2, 1.2, ["AWS lo midió con TPC-DS y TPC-H a **10 TB en nodos rg.4xlarge**. Nosotros, con 100 GB en un clúster de 2 nodos xlarge."],
            size=24, color=WHITE)
    textbox(s, X0, Y0 + 5.15, 15.2, 0.6, ["Fuente: blog de AWS Big Data «Meet Amazon Redshift RG…», 19 de mayo de 2026."], size=16, color=MUTED)
    notes(s, "Estos son los cuatro números del anuncio, y son los que vamos a revisar. Fíjense en la última línea: AWS midió 10 TB en nodos grandes. Yo medí un clúster chico, más parecido al que tienen muchos equipos.")

    # 9 transition
    set_transition(S[8], "CÓMO LO", "MEDIMOS")
    notes(S[8], "Antes de mostrar un solo número, les cuento cómo lo obtuve, porque una comparación sin método es solo una opinión con decimales.")

    # 10 architecture
    s = S[9]
    set_title(s, "El laboratorio")
    picture(s, ROOT / "slides/assets/arquitectura-lab.png", X0, Y0 + 0.05, 15.6, 5.75)
    notes(s, "Armé una VPC propia, con enhanced VPC routing y endpoints para S3, Glue, Lake Formation y S3 Tables. El clúster RA3 tiene 2 nodos ra3.xlplus, y el RG, 2 nodos rg.xlarge, creado a partir del mismo snapshot: los dos tienen exactamente los mismos datos. El data lake está en S3, con tablas Iceberg y Parquet registradas en Glue. RA3 lee esos datos con Spectrum, que corre fuera de la VPC; RG los lee con sus propios nodos, desde la VPC. Las consultas las lanza un programa en Python a través de la Data API, y la infraestructura la crea GitHub Actions con OIDC, sin claves guardadas en ningún lado.")

    # 11 method
    s = S[10]
    set_title(s, "Una comparación justa")
    textbox(s, X0, Y0, 15.2, 5.8, ["Los dos clústeres arrancan del mismo snapshot y con la misma versión de Redshift (1.0.434008)",
                                    "Sin caché de resultados y sin escalado automático de concurrencia",
                                    "Los tiempos los mide Redshift (SYS_QUERY_HISTORY), no mi computadora",
                                    "Cada consulta se repite tres veces: la primera no cuenta y nos quedamos con la mediana",
                                    "**Si alguna consulta usa la caché, la prueba entera se descarta. En este laboratorio no se descartó ninguna.**"],
            size=25, bullets=True, space=20)
    notes(s, "Lo más importante es el último punto: el programa revisa cada consulta y, si alguna usó la caché de resultados, descarta la prueba completa. No hubo que descartar ninguna.")

    # 12 what we did not test
    s = S[11]
    set_title(s, "Lo que no probamos")
    outs = [("100 GB, no 10 TB", "Con pocos datos, el costo fijo de cada consulta pesa más"),
            ("Solo el tamaño xlarge", "No probamos 4xlarge ni 12xlarge"),
            ("Serverless solo a 4 RPU", "Capacidad fija para comparar; no probamos cómo escala"),
            ("S3 Tables", "No lo pudimos probar; más adelante les cuento por qué")]
    for i, (t, b) in enumerate(outs):
        card(s, X0 + (i % 2) * 7.85, Y0 + (i // 2) * 2.95, 7.55, 2.65, t, b, size=22, title_color=ORANGE)
    notes(s, "Prefiero decirlo desde el principio. Con 100 GB, buena parte de los datos que se consultan cabe en memoria, y eso reduce la ventaja de RG cuando hay que leer mucho. Si aun así RG gana, es buena señal; con más datos esperaría una diferencia mayor, pero eso no lo medí. Serverless lo medimos solo con 4 RPU fijos, sin dejarlo escalar.")

    # 13 transition
    set_transition(S[12], "WAREHOUSE")
    notes(S[12], "Empecemos por lo básico de cualquier warehouse: consultas sobre sus propias tablas.")

    # 14 performance chart
    s = S[13]
    set_title(s, f"RG fue {geo}x más rápido")
    srt = sorted(pr, key=lambda r: -r[3])
    bar_chart(s, X0 - 0.1, Y0 - 0.1, 10.2, 6.2, [r[0] for r in srt], [("Aceleración RG", [r[3] for r in srt])],
              [ACCENT], horizontal=True, fmt='0.00"x"', label_size=13, axis_size=13, gap=35, label_fn=lambda v: es(v, 2) + "x",
              point_colors=[ACCENT if cls[r[0]] == "scan" else ORANGE for r in srt])
    lg = textbox(s, 11.1, Y0 + 0.05, 5.8, 0.9, ["Cuántas veces más rápido fue RG en cada consulta"], size=17, color=SOFT).text_frame
    p = lg.add_paragraph()
    _runs(p, "■ lectura   ", 17, ACCENT)
    _runs(p, "■ cálculo", 17, ORANGE)
    pair_stat(s, 11.1, Y0 + 1.25, 5.8, "Tiempo total de las 20 consultas", float(ps["tot"][0]), float(ps["tot"][1]))
    pair_stat(s, 11.1, Y0 + 3.75, 5.8, "Una consulta típica (mediana)", float(ps["p50"][0]), float(ps["p50"][1]), nd=2, note=None)
    notes(s, f"Veinte consultas, cada una repetida tres veces, sin contar la primera. RG fue más rápido en las veinte. La que más mejoró, query48, fue 3,58 veces más rápida; la que menos, query57, 1,08 veces. En promedio, usando la media geométrica, que es la forma correcta de promediar este tipo de comparaciones, RG fue {geo} veces más rápido. Para el total de las veinte consultas: RA3 tardó 148 segundos y RG, 97. En azul, las consultas que leen y agregan muchos datos; en naranja, las de cálculo pesado.")

    # 15 read vs compute
    s = S[14]
    set_title(s, "Donde más gana: leer y agregar")
    stat(s, X0, Y0 + 0.35, 7.6, f"{es(float(ps['scan']), 2)}x", "consultas que leen y agregan muchos datos (10 consultas)", size=120)
    stat(s, X0 + 8.1, Y0 + 0.35, 7.6, f"{es(float(ps['cpu']), 2)}x", "consultas de cálculo pesado: funciones de ventana y joins grandes (10 consultas)", size=120, color=ORANGE)
    textbox(s, X0, Y0 + 4.5, 15.2, 1.0, ["AWS anuncia hasta 2,2x: **en las consultas de lectura lo superamos; en las de cálculo, no llegamos.**"], size=25, color=WHITE)
    notes(s, "Separé las consultas en dos grupos antes de ejecutarlas, no después. Las que leen muchos datos y los agregan mejoraron 2,28 veces: ahí es donde Graviton y el ancho de banda de memoria hacen la diferencia. Las de cálculo pesado, con funciones de ventana y joins de quince tablas, mejoraron 1,58 veces. Si tu warehouse es sobre todo dashboards y reportes con agregaciones, estás en el lado que más gana.")

    # 16 concurrency
    s = S[15]
    set_title(s, f"Varios usuarios a la vez: {es(rg_q / ra3_q)}x", 50)
    bar_chart(s, X0, Y0 - 0.2, 9.0, 6.0, ["RA3", "RG"], [("Consultas por hora", [ra3_q, rg_q])], [ACCENT],
              fmt='0', point_colors=[RA3C, ACCENT], label_size=28, axis_size=24, gap=80, label_fn=lambda v: str(int(v)))
    textbox(s, 10.6, Y0 + 0.6, 6.2, 4.5, ["**Consultas por hora** (más es mejor)", "Cinco usuarios simulados durante 30 minutos",
                                           "Ninguna consulta quedó en espera", "Ningún error"], size=25, space=18)
    notes(s, f"Simulé cinco usuarios lanzando las mismas veinte consultas, en distinto orden, durante media hora. RG completó {int(rg_q)} consultas por hora y RA3, {int(ra3_q)}. En ninguno de los dos hubo consultas en espera.")

    # 17 load and ELT
    s = S[16]
    set_title(s, "Carga y transformación")
    textbox(s, X0, Y0 + 0.1, 6.6, 5.6, ["**Cargar los 100 GB tomó 20 min 44 s**", "Desde S3, en RA3, una sola vez",
                                        f"Copiar una tabla desde S3: **{es(elt_a['ecopy']/elt_g['ecopy'], 2)}x**",
                                        f"Crear una tabla resumen (CTAS): **{es(elt_a['ectas']/elt_g['ectas'], 2)}x**"], size=25, space=18)
    bar_chart(s, X0 + 7.0, Y0 - 0.2, 8.6, 6.0, ["Copiar store_returns", "Tabla resumen (CTAS)"],
              [("RA3", [elt_a["ecopy"], elt_a["ectas"]]), ("RG", [elt_g["ecopy"], elt_g["ectas"]])],
              [RA3C, ACCENT], fmt='0.0" s"', legend=True, label_size=20, axis_size=20, label_fn=lambda v: es(v) + " s")
    notes(s, "La carga inicial la hice una sola vez, en RA3, y RG se creó a partir del snapshot. La prueba de transformación repite una copia desde S3 y la creación de una tabla resumen en los dos clústeres: RG fue 1,5 y 1,6 veces más rápido. Cada una se ejecutó dos veces, así que lo tomo como tendencia, no como número exacto.")

    # 18 cost
    s = S[17]
    set_title(s, "Más rápido y también más barato")
    ua, ug = float(ps["usd"][0]), float(ps["usd"][1])
    stat(s, X0, Y0 + 0.2, 9.0, f"USD {es(ua, 3)} → {es(ug, 3)}", "lo que costó cada ejecución de las 20 consultas", size=54, color=WHITE)
    stat(s, X0 + 9.2, Y0 + 0.2, 6.2, f"{es(ua / ug)}x", "menos costo por el mismo trabajo", size=110)
    textbox(s, X0, Y0 + 4.4, 15.2, 1.2, ["Dos razones que se suman: **el nodo RG cuesta 30 % menos por hora y además termina antes.**"], size=25, color=WHITE)
    notes(s, "Esto es lo que más le interesa a quien paga la factura. No solo el nodo es más barato: como termina antes, cada ejecución cuesta menos de la mitad.")

    # 19 serverless
    s = S[18]
    set_title(s, "¿Y Serverless?")
    sa, sg, ss = per_q("rr-ra3-power-c7cb"), per_q("rr-rg-power-4628"), per_q("rr-sls-power-97ac")
    sl = per_q("rr-sls-lake-glue-d3bd")
    rows = [["", "RA3", "RG", "Serverless 4 RPU"],
            ["20 consultas (total)", f"{es(sum(sa.values()))} s", f"**{es(sum(sg.values()))} s**", f"{es(sum(ss.values()))} s"],
            ["Consultas por hora, 5 usuarios", str(int(ra3_q)), f"**{int(rg_q)}**", str(int(qph("rr-sls-concurrency-cdef")))],
            ["Iceberg (6 consultas)", f"{es(sum(ice_a.values()))} s", f"**{es(sum(ice_g.values()))} s**", f"{es(sum(sl.values()))} s"],
            ["Costo por ejecución de las 20", "USD 0,089", "**USD 0,041**", "USD 0,102"]]
    table(s, X0, Y0, 15.2, rows, [5.0, 3.0, 3.0, 4.2], size=22, row_h=0.7)
    textbox(s, X0, Y0 + 3.75, 15.2, 1.8, [f"Con la misma memoria (64 GB) y casi el mismo precio por hora, **RG fue {es(stats.geomean(stats.speedups(ss, sg).values()), 1)} veces más rápido que Serverless de 4 RPU.**",
                                          "La capacidad quedó fija a propósito: la ventaja de Serverless es escalar cuando hace falta y no cobrar sin consultas."],
            size=22, space=12)
    notes(s, "Agregué Serverless con la misma memoria que el clúster RG: 4 RPU son 64 GB, y cuestan 1,50 dólares por hora contra 1,52 del clúster. Fijé la capacidad para que no escalara durante la prueba. En esas condiciones, RG fue unas tres veces más rápido en las consultas del warehouse, y Serverless quedó incluso por debajo de RA3 en casi todo. Pero ojo con la conclusión: 4 RPU es el tamaño de entrada, y lo que vende Serverless es otra cosa: escalar solo cuando hace falta y no cobrar cuando no hay consultas. Todas las pruebas de Serverless del día costaron 1,48 dólares. Fuente: results/2026-10-05/summary-serverless.md.")

    # 20 transition
    set_transition(S[19], "DATA", "LAKE")
    notes(S[19], "Ahora la parte más interesante, y la que más depende de cómo tienes guardados tus datos.")

    # 20 three ways
    s = S[20]
    set_title(s, "El mismo dato, de tres formas")
    for i, (t, b) in enumerate([("Local", "Tablas dentro del warehouse"), ("Iceberg", "Tablas Iceberg en S3, registradas en Glue"),
                                ("Parquet", "Archivos Parquet en S3, registrados en Glue")]):
        card(s, X0 + i * 5.2, Y0, 4.9, 2.9, t, b, size=22, title_size=36, title_color=ACCENT)
    textbox(s, X0, Y0 + 3.4, 15.2, 2.4, ["Las mismas 6 consultas en las tres versiones devuelven **exactamente las mismas 483 filas**.",
                                          "RA3 lee S3 a través de **Spectrum**, fuera de tu VPC; RG lo lee **con sus propios nodos**, dentro de tu VPC."],
            size=24, space=14)
    notes(s, "Escribí las mismas cinco tablas en Iceberg y en Parquet desde el warehouse, y comprobé que las seis consultas devuelven exactamente las mismas 483 filas en las tres versiones. Así, lo único que cambia es la forma de leer los datos.")

    # 21 iceberg
    s = S[21]
    ia, ig = sum(ice_a.values()), sum(ice_g.values())
    set_title(s, f"Iceberg: {es(stats.geomean(stats.speedups(ice_a, ice_g).values()), 2)}x, ya con caché", 48)
    qs = sorted(ice_a)
    bar_chart(s, X0 - 0.1, Y0 - 0.2, 9.6, 6.1, qs, [("RA3", [ice_a[q] for q in qs]), ("RG", [ice_g[q] for q in qs])],
              [RA3C, ACCENT], fmt='0.0" s"', legend=True, label_size=15, axis_size=17, label_fn=lambda v: es(v) + " s")
    pair_stat(s, 11.0, Y0 + 0.1, 5.8, "Tiempo total de las 6 consultas", ia, ig)
    textbox(s, 11.0, Y0 + 2.9, 5.8, 2.8, ["**Ojo:** la primera vez que RG lee los datos tarda hasta 27 s. Desde la segunda, unos 2 s, porque los guarda en caché."],
            size=21, color=ORANGE)
    notes(s, "RG lee Iceberg casi dos veces más rápido que RA3, con una salvedad: la primera vez que toca los datos tarda bastante más, porque los trae de S3 y los guarda en caché. Mi método no cuenta la primera repetición, así que este resultado es con la caché ya cargada. Si consultas el data lake de vez en cuando, ten en cuenta esa primera lectura.")

    # 22 parquet
    s = S[22]
    set_title(s, "Parquet: los archivos importan", 50)
    rows = [["Parquet store_sales", "RA3 (total)", "RG (total)", "RG frente a RA3 (media geom.)"],
            ["4 archivos de ≈3,8 GB", f"{es(pq1[0])} s", f"{es(pq1[1])} s", f"**{es(pq1[2], 2)}x**"],
            ["31 archivos de ≈0,5 GB", f"{es(pq2[0])} s", f"{es(pq2[1])} s", f"**{es(pq2[2], 2)}x**"]]
    table(s, X0, Y0, 15.2, rows, [4.8, 2.6, 2.6, 5.2], size=24, row_h=0.95)
    textbox(s, X0, Y0 + 3.3, 15.2, 2.6, ["Los dos clústeres usan **exactamente el mismo plan de ejecución**.",
                                          "Partir los archivos en pedazos más chicos **ayuda a RG y perjudica a RA3**.",
                                          "Lo repetimos una sola vez: la tendencia es clara; el número exacto, no tanto."], size=24, space=14)
    notes(s, "Este fue el resultado que más me sorprendió. Con Parquet, RG empezó siendo más lento que RA3. Revisé el plan de ejecución y era idéntico en los dos. La diferencia estaba en los archivos: Redshift los había escrito en solo cuatro archivos enormes, uno por slice, porque por defecto cada archivo puede llegar a 6.200 MB. Los reescribí en archivos de medio giga y RG pasó a ganar, mientras que RA3 empeoró. El mismo cambio ayuda a uno y perjudica al otro.")

    # 23 spectrum cost
    s = S[23]
    set_title(s, "Spectrum cobra aparte")
    stat(s, X0, Y0 + 0.1, 5.0, "USD 0,083", "18,2 GB leídos de Iceberg (2 repeticiones)", size=60, color=ORANGE)
    stat(s, X0 + 5.2, Y0 + 0.1, 5.0, "USD 0,092", "20,2 GB leídos de Parquet (2 repeticiones)", size=60, color=ORANGE)
    stat(s, X0 + 10.4, Y0 + 0.1, 4.8, "USD 0", "por lectura en RG", size=60, color=ACCENT)
    textbox(s, X0, Y0 + 3.9, 15.2, 1.5, ["En RA3 se pagan USD 5 por cada TB leído. **Multiplícalo por todo lo que consultas del data lake en un mes.**"], size=25, color=WHITE)
    notes(s, "En el laboratorio son centavos, porque son 100 GB. Pero esto crece con el volumen y con la frecuencia: un equipo que lee decenas de TB al mes desde el data lake lo nota en la factura. En RG ese cobro desaparece.")

    # 24 lessons
    s = S[24]
    set_title(s, "Lo que aprendimos del data lake")
    les = [("S3 Tables pide IAM", "cross-database reference to database \"…@s3tablescatalog\" is not supported"),
           ("Iceberg no acepta CHAR", "CHAR type is not supported for column \"d_date_id\" in Iceberg table creation"),
           ("Lake Formation manda", "Insufficient Lake Formation permission(s): Required Create Table on rr_iceberg")]
    for i, (t, e) in enumerate(les):
        c = card(s, X0 + i * 5.2, Y0, 4.9, 3.4, t, [], size=20, title_size=26, title_color=ORANGE)
        p = c.text_frame.add_paragraph()
        r = p.add_run()
        r.text = e
        r.font.name, r.font.size, r.font.color.rgb = "Courier New", Pt(17), SOFT
    textbox(s, X0, Y0 + 3.9, 15.2, 1.0, ["Si vas a usar S3 Tables desde Redshift, **decide primero cómo se van a autenticar tus usuarios.**"], size=24, color=WHITE)
    notes(s, "Quería probar S3 Tables y no pude, por una razón de diseño: esas tablas solo se leen conectándose con una identidad de IAM, y mi programa se conecta con un usuario de base de datos. Cambiar de usuario solo para esa prueba habría medido otra cosa. Además, Iceberg no acepta columnas CHAR, y Lake Formation exige permisos explícitos sobre las bases de Glue.")

    # 25 transition
    set_transition(S[25], "LA", "MIGRACIÓN")
    notes(S[25], "Supongamos que decides migrar. ¿Cuánto cuesta en tiempo y en sustos?")

    # 26 drill timeline
    s = S[26]
    set_title(s, "La migración tomó 2 min 48 s")
    probes = [{"ts": "2026-10-05T19:05:47Z", "write_probe": "START"}] + list(csv.DictReader(open(R / "drill-log.csv")))  # start from drill.md
    n = len(probes)
    line_y = Y0 + 1.9
    ln = s.shapes.add_connector(1, Inches(X0 + 0.3), Inches(line_y), Inches(X0 + 15.0), Inches(line_y))
    ln.line.color.rgb, ln.line.width = MUTED, Pt(3)
    for i, row in enumerate(probes):
        cx = X0 + 0.3 + i * 14.7 / (n - 1)
        ok, start = row["write_probe"] == "FINISHED", row["write_probe"] == "START"
        dot = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx - 0.28), Inches(line_y - 0.28), Inches(0.56), Inches(0.56))
        dot.fill.solid(), setattr(dot.fill.fore_color, "rgb", WHITE if start else (ACCENT if ok else ORANGE))
        dot.line.fill.background()
        textbox(s, cx - 1.1, line_y - 1.3, 2.2, 0.6, [row["ts"][11:19]], size=18, color=SOFT, align=PP_ALIGN.CENTER)
        textbox(s, cx - 1.2, line_y + 0.45, 2.4, 0.9, ["inicio" if start else ("se puede escribir" if ok else "solo lectura")], size=17,
                color=WHITE if start else (RGBColor(0x8F, 0xB4, 0xFF) if ok else ORANGE), align=PP_ALIGN.CENTER, bold=True)
    stat(s, X0, Y0 + 3.0, 7.6, "1:35 a 2:42", "minutos sin poder escribir (lo revisamos cada 30 s)", size=60, color=ORANGE)
    stat(s, X0 + 8.1, Y0 + 3.0, 7.4, "Sin cambios", "en cómo se reparten los datos entre nodos", size=60, color=ACCENT)
    notes(s, "Restauré una copia del clúster RA3 y lo convertí a RG con un elastic resize, intentando escribir cada 30 segundos. Empezó a las 19:05:47 y terminó a las 19:08:35. El clúster quedó en solo lectura entre 1 minuto 35 y 2 minutos 42 segundos; el rango se debe a que revisábamos cada 30 segundos. Como pasamos de 2 nodos a 2 nodos, los datos quedaron repartidos igual. Ojo: si cambias la cantidad de nodos, como al pasar de 4 a 3 en el tamaño 4xlarge, el reparto sí puede desbalancearse.")

    # 27 traps
    s = S[27]
    set_title(s, "Lo que nadie te cuenta")
    traps = ["**La contraseña administrada:** para restaurar el snapshot hay que volver a pedirla con ‑‑manage‑master‑password",
             "**Primero, un snapshot:** un clúster recién restaurado no acepta el resize hasta tener un snapshot propio",
             "**«Disponible» no es lo mismo que listo:** el estado dice available, pero otro campo sigue en Modifying y el resize falla",
             "**De 4 a 3 nodos:** cambiar la cantidad de nodos puede desbalancear los datos",
             "**Restaurar cambia el endpoint:** si migras desde un snapshot, hay que reconfigurar zero-ETL, DMS y datashares"]
    textbox(s, X0, Y0, 15.2, 5.9, traps, size=23, bullets=True, space=16)
    notes(s, "Las tres primeras me pasaron en el simulacro, en ese orden, y no las encontré en la guía de migración. Las dos últimas sí aparecen en la documentación y en el blog de AWS. Todas quedaron resueltas en el script del repositorio.")

    # 28 transition
    set_transition(S[28], "DEMO")
    notes(S[28], "Ahora veamos las consultas y los datos reales.")

    # 29 demo query
    s = S[29]
    set_title(s, "Demo: una consulta, dos clústeres", 50)
    code(s, X0, Y0, 10.2, 4.3, "SELECT count(*)\nFROM store_sales, household_demographics,\n     time_dim, store\n"
         "WHERE ss_sold_time_sk = time_dim.t_time_sk\n  AND ss_hdemo_sk = household_demographics.hd_demo_sk\n"
         "  AND ss_store_sk = s_store_sk\n  AND time_dim.t_hour = 15\n  AND time_dim.t_minute >= 30\n"
         "  AND household_demographics.hd_dep_count = 7\n  AND store.s_store_name = 'ese'\nLIMIT 100;", size=17)
    textbox(s, X0, Y0 + 4.5, 10.2, 1.4, ["**Por qué pesa:** recorre las 288 millones de ventas de store_sales y las cruza con tres tablas para quedarse con una franja horaria y un tipo de hogar."],
            size=20, color=SOFT)
    pair_stat(s, 11.6, Y0 + 0.3, 5.0, "query96", q96[1], q96[2], nd=2)
    textbox(s, 11.6, Y0 + 3.0, 5.0, 1.2, [f"RG fue **{es(q96[3], 2)}x** más rápido"], size=28, color=WHITE)
    notes(s, "Esta es una consulta típica de lectura: cuenta ventas filtrando por hora del día, por tipo de hogar y por tienda. Lo pesado es que tiene que recorrer las 288 millones de filas de la tabla de ventas y cruzarlas con tres tablas más. En RA3 tarda 1,77 segundos; en RG, 0,67.")

    # 30 demo explain
    s = S[30]
    set_title(s, "Demo: el mismo plan en los dos", 50)
    code(s, X0, Y0, 7.6, 3.3, "RA3  (lq3 sobre Parquet)\n\nXN Hash Join DS_BCAST_INNER\n  XN Hash Join DS_BCAST_INNER\n"
         "    XN S3 Query Scan ss\n      S3 Seq Scan pq.store_sales\n         rows=287997024", size=17)
    code(s, X0 + 7.8, Y0, 7.6, 3.3, "RG  (lq3 sobre Parquet)\n\nXN Hash Join DS_BCAST_INNER\n  XN Hash Join DS_BCAST_INNER\n"
         "    XN Seq Scan pq.store_sales\n       format:PARQUET\n         rows=287997024", size=17)
    textbox(s, X0, Y0 + 3.75, 15.2, 1.3, ["Mismos joins y mismas estimaciones de filas. **Lo único que cambia es quién lee los datos de S3.**"],
            size=24, color=WHITE)
    notes(s, "Así encontré la explicación del caso de Parquet. Si los planes fueran distintos, la diferencia estaría en el plan y no en el clúster. Son iguales: lo único que cambia es la pieza que lee S3, Spectrum en RA3 y los propios nodos en RG. Cuando veas una diferencia rara entre dos clústeres, empieza por aquí.")

    # 31 demo results page
    s = S[31]
    set_title(s, "Demo: todos los resultados")
    shot = ROOT / "slides/assets/resultados-captura.png"
    if shot.exists():
        picture(s, shot, X0, Y0 + 0.15, 10.0, 5.6)
        tx = 11.6
    else:
        tx = X0
    textbox(s, tx, Y0 + 0.2, 16.4 - tx, 5.4, ["Una página con todos los números de la charla:",
                                              "Cuánto mejoró RG en cada consulta", "El data lake antes y después de reescribir los archivos Parquet",
                                              "La línea de tiempo de la migración"], size=23, space=16)
    notes(s, "Esta página reúne todos los números de la charla, sacados directamente de los archivos del repositorio. La abro un momento para que vean cada consulta. Abrir: https://claude.ai/artifact/1MgMakVPq4URRXQMZp4aVk (privada, con la sesión del orador; copia local: slides/demo/resultados.html).")

    # 32 decision
    s = S[32]
    set_title(s, "¿Migrar o no migrar?")
    cols = [("Migra si", ["Tus consultas leen y agregan muchos datos (dashboards, reportes)", "Consultas seguido el data lake", "Usas xlplus o 4xlarge: pagas 30 % menos por vCPU"], ACCENT),
            ("Prueba antes si", ["Tus consultas son de cálculo pesado (ventanas, joins grandes)", "Tu data lake está en Parquet con archivos grandes", "Quieres usar S3 Tables con usuarios de base de datos"], ORANGE),
            ("Mira Serverless si", ["Usas Redshift solo a ratos", "No quieres administrar un clúster", "A 4 RPU fue 3 veces más lento que RG: dale más capacidad"], RA3C)]
    for i, (t, items, col) in enumerate(cols):
        card(s, X0 + i * 5.2, Y0, 4.9, 4.4, t, ["• " + x for x in items], size=21, title_size=30, title_color=col)
    notes(s, "Esta es mi respuesta a la pregunta del título. Para la mayoría de los equipos con RA3, migrar conviene: es más rápido, más barato y el cambio toma minutos. Pero prueba primero con tus datos, sobre todo si tu data lake está en Parquet o si tus consultas son de cálculo pesado. Serverless es otra decisión, que depende de cómo usas Redshift: a 4 RPU fijos fue mucho más lento que RG, así que si lo eliges, dale más capacidad o deja que escale.")

    # 33 take the lab
    s = S[33]
    set_title(s, "Llévate el laboratorio")
    textbox(s, X0, Y0 + 0.1, 11.6, 1.2, ["github.com/andrezc98/redshift-redemption"], size=36, color=ACCENT, bold=True)
    qr(s, ROOT / "slides/assets/qr-github.png", 13.2, Y0 + 0.35, 3.3, "Escanea para ir al repo")
    textbox(s, X0, Y0 + 1.6, 11.6, 4.0, ["La infraestructura, con Terraform y GitHub Actions (OIDC)",
                                          "El programa de pruebas, en Python, y el runbook paso a paso",
                                          "Todos los resultados, con su método, en la carpeta results/",
                                          "Repetirlo con 100 GB toma un día de trabajo y unas decenas de dólares"], size=25, bullets=True, space=18)
    notes(s, "Todo lo que vieron está en el repositorio: la infraestructura, el programa que lanza las pruebas, el runbook con cada paso y los errores que me encontré. Cámbienle el dataset por el suyo y repitan las mediciones.")

    # 35 quiz (talk questions) and 36 kahoot (simpler ones), per the organizers' email
    for slide, title, qs in ((S[34], "Quiz", QUIZ), (S[35], "Kahoot", KAHOOT)):
        set_title(slide, title)
        n = len(qs)
        w = (15.2 - 0.3 * (n - 1)) / n
        for i, q in enumerate(qs):
            card(slide, X0 + i * (w + 0.3), Y0, w, 3.4, f"Pregunta {i + 1}", q["q"], size=21, title_size=24, title_color=ACCENT)
        textbox(slide, X0, Y0 + 3.9, 15.2, 1.0, ["Las respuestas y los comentarios están en las notas."], size=20, color=MUTED)
        notes(slide, f"{title}. " + " ".join(
            f"Pregunta {i + 1}: {q['q']} " + "; ".join(f"{'abcd'[j]}) {o}" + (" (correcta)" if j == q['ok'] else "") for j, o in enumerate(q['opts']))
            + f". Comentario: {q['why']}" for i, q in enumerate(qs)))

    # 37 thanks
    s = S[36]
    set_title(s, "¡Gracias!", 72)
    textbox(s, X0, Y0 + 0.4, 8.6, 4.5, ["**Andrés Zeballos**", "Solutions Architect en phData",
                                         "LinkedIn: linkedin.com/in/andreszc",
                                         "GitHub: andrezc98"], size=28, space=20)
    qr(s, ROOT / "slides/assets/qr-linkedin.png", 10.0, Y0 + 0.35, 3.0, "LinkedIn")
    qr(s, ROOT / "slides/assets/qr-github.png", 13.6, Y0 + 0.35, 3.0, "El laboratorio")
    notes(s, "Gracias. Respondo preguntas en el chat. Si alguien pregunta por Snowflake u otras plataformas: trabajo con varias y son buenas respuestas para contextos distintos; hoy vine a medir la decisión que ya tienen enfrente los equipos que usan AWS: RA3 o RG.")


def write_preguntas():
    """slides/preguntas.md: quiz and Kahoot questions to send with the deck."""
    out = ["# Preguntas para el quiz y el Kahoot", "",
           "Charla «Redshift Redemption: los nuevos nodos RG, ¿migrar o no migrar?». Generado por",
           "`slides/build_deck.py`. La respuesta correcta está marcada con ✅.", ""]
    for title, qs in (("Quiz (preguntas sobre la charla)", QUIZ), ("Kahoot (preguntas sencillas)", KAHOOT)):
        out += [f"## {title}", ""]
        for i, q in enumerate(qs, 1):
            out.append(f"**{i}. {q['q']}**")
            out += [f"- {'abcd'[j]}) {o}" + (" ✅" if j == q["ok"] else "") for j, o in enumerate(q["opts"])]
            out += ["", f"Comentario: {q['why']}", ""]
    (ROOT / "slides/preguntas.md").write_text("\n".join(out))


def write_contenido(prs):
    """slides/contenido.md is generated from the deck: on-slide text and speaker notes per slide."""
    skip = ("HOY:", "Episodio II", "OCTUBRE", "Mes de", "HAN SOLO", "User Groups")
    out = ["# Redshift Redemption — contenido de las diapositivas", "",
           "Generado por `slides/build_deck.py` a partir del deck; no se edita a mano (cambia el script y",
           "reconstruye). Charla: «Redshift Redemption: los nuevos nodos RG, ¿migrar o no migrar?», AWS Women",
           "Colombia User Group, Episodio II, 2026-10-08. Cada número sale de `results/2026-10-05/` y",
           "`results/prices.md`; las fuentes externas se citan en la diapositiva o en sus notas.", ""]
    for i, slide in enumerate(prs.slides, 1):
        texts = []
        for sh in slide.shapes:
            if sh.has_text_frame:
                for p in sh.text_frame.paragraphs:
                    t = "".join(r.text for r in p.runs).strip()
                    if t and not t.startswith(skip):
                        texts.append(t)
            elif sh.has_table:
                for row in sh.table.rows:
                    texts.append(" | ".join(c.text for c in row.cells))
            elif sh.has_chart:
                ch = sh.chart
                texts.append("[gráfico: " + ", ".join(f"{s.name}" for s in ch.plots[0].series) + "]")
            elif sh.shape_type == 13:
                texts.append("[imagen]")
        out.append(f"## {i}")
        out += [f"- {t}" for t in texts]
        out += ["", "**Notas:** " + slide.notes_slide.notes_text_frame.text, ""]
    (ROOT / "slides/contenido.md").write_text("\n".join(out))



def main():
    skill = Path(sys.argv[1])
    with tempfile.TemporaryDirectory() as tmp:
        structure = build_structure(skill, Path(tmp))
        prs = Presentation(str(structure))
        assert len(prs.slides) == len(SRC), len(prs.slides)
        fill(prs)
        prs.save(str(OUT))
        write_contenido(prs)
        write_preguntas()
    print(f"wrote {OUT} ({len(SRC)} slides)")


if __name__ == "__main__":
    main()
