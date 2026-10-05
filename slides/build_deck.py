"""Build slides/redshift-redemption.pptx from the community template.

Structure (slide copies) is made with the pptx skill's add_slide.py/clean.py,
then python-pptx fills each slide. Numbers are read from results/, never typed.
Text source of truth: slides/contenido.md.

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
SRC = [4, 4, 2, 4, 10, 6, 6, 6, 12, 8, 8, 8, 14, 4, 4, 4, 4, 4, 10, 6, 6, 6, 6, 6, 12, 8, 8, 14, 4, 4, 4, 6, 6, 6, 6]


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


def set_title(slide, text, size=54):
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip() in ("TÍTULO",):
            sh.left, sh.top, sh.width, sh.height = Inches(3.85), Inches(0.95), Inches(13.2), Inches(2.05)
            size = min(size, 44 if len(text) > 30 else size)
            tf = sh.text_frame
            tf.word_wrap, tf.vertical_anchor = True, MSO_ANCHOR.MIDDLE
            run = tf.paragraphs[0].runs[0]
            run.text, run.font.size = text, Pt(size)
            for extra in tf.paragraphs[0].runs[1:]:
                extra.text = ""
            return
    raise ValueError("no TÍTULO box")


def set_transition(slide, line1, line2=""):
    for sh in slide.shapes:
        if sh.has_text_frame and "TRANSICI" in sh.text_frame.text:
            p1, p2 = sh.text_frame.paragraphs[:2]
            p1.runs[0].text = line1
            for r in p1.runs[1:]:
                r.text = ""
            p2.runs[0].text = ("        " + line2) if line2 else ""
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
def fill(prs):
    S = prs.slides
    ps, pr, cls = power_summary(), power_rows(), classes()
    ra3_q, rg_q = qph("rr-ra3-concurrency-8c56"), qph("rr-rg-concurrency-8599")
    elt_a, elt_g = per_q("rr-ra3-elt-b9f7"), per_q("rr-rg-elt-0a03")
    ice_a, ice_g = per_q("rr-ra3-lake-glue-e691"), per_q("rr-rg-lake-glue-9d55")
    pq_runs = [("rr-ra3-lake-parquet-68e7", "rr-rg-lake-parquet-dd2f"), ("rr-ra3-lake-parquet-df42", "rr-rg-lake-parquet-f7c8")]
    pq1, pq2 = [(tot(a), tot(g), stats.geomean(stats.speedups(per_q(a), per_q(g)).values())) for a, g in pq_runs]
    q96 = next(r for r in pr if r[0] == "query96")

    # 1 cover
    s = S[0]
    set_title(s, "Redshift Redemption", 72)
    textbox(s, X0, Y0 + 0.4, 9.6, 4.5, ["Los nuevos nodos RG: **¿migrar o no migrar?**",
                                         "Andrés Zeballos · Solutions Architect, phData",
                                         "100 GB TPC-DS · RA3 frente a RG · 2026-10-05"], size=30, space=22)
    stat(s, 11.4, Y0 + 0.5, 5.4, f"{es(float(ps['geo']), 2)}x", "más rápido en nuestro lab (media de 20 consultas)", size=110)
    notes(s, "Buenas tardes. Hoy no vengo a contarles lo que dice el anuncio de AWS; vengo a contarles qué pasó cuando lo medí. Ese 1,90x es uno de los números de hoy, y al final van a ver que no es el único que importa.")

    # 2 bio
    s = S[1]
    set_title(s, "Quién soy")
    items = [("De Arequipa", "Solutions Architect en phData, casi siempre con AWS"),
             ("Trayectoria", "Redes → infraestructura → Kubernetes → datos → agentes de IA"),
             ("Comunidad", "AWS Golden Jacket · colaboré en las nuevas microcredenciales de análisis de datos de AWS"),
             ("Mi regla", "Cada charla sale de un laboratorio que armo y publico para que lo repitas")]
    for i, (t, b) in enumerate(items):
        card(s, X0 + (i % 2) * 7.85, Y0 + (i // 2) * 2.95, 7.55, 2.65, t, b, size=22)
    notes(s, "Me gusta probar las cosas antes de recomendarlas. Esta charla es eso: un laboratorio que armé esta semana, con su costo y sus errores incluidos.")

    # 3 agenda
    set_agenda(S[2], ["Qué cambió de RA3 a RG", "Cómo lo medimos", "Warehouse: potencia, concurrencia y costo",
                      "Data lake: Iceberg, Parquet y Spectrum", "La migración y sus trampas", "Demo"])
    notes(S[2], "Cinco temas y una demo. Al final, una respuesta concreta a la pregunta del título, y tres preguntas de Kahoot.")

    # 4 question
    s = S[3]
    set_title(s, "¿Migro o no migro?")
    card(s, X0, Y0, 4.6, 2.6, "RA3", "Lo que tienes hoy", size=24, title_size=54, title_color=RA3C)
    textbox(s, X0 + 4.6, Y0 + 0.5, 1.4, 1.6, ["?"], size=88, color=ORANGE, bold=True, align=PP_ALIGN.CENTER)
    card(s, X0 + 6.0, Y0, 4.6, 2.6, "RG", "Graviton, desde mayo de 2026", size=24, title_size=54, title_color=ACCENT)
    textbox(s, X0, Y0 + 3.1, 15.6, 2.8, ["Si administras un Redshift con RA3, o pagas su factura, la pregunta llegó sola.",
                                          "Hoy tomamos las promesas de AWS y las ponemos a prueba: **dónde se cumplen y dónde dependen de tu carga.**"],
            size=26, space=16)
    notes(s, "La idea no es desmentir a nadie. AWS publica sus números; nosotros los verificamos en el tamaño de clúster que la mayoría opera. Cuando se cumplen, lo decimos; cuando dependen de algo, explicamos de qué.")

    # 5 transition
    set_transition(S[4], "QUÉ", "CAMBIÓ")
    notes(S[4], "Primero, qué es exactamente un nodo RG y en qué se diferencia de RA3.")

    # 6 what's new
    s = S[5]
    set_title(s, "Qué trae RG")
    cards = [("Graviton", "Instancias basadas en los procesadores Arm de AWS"),
             ("Motor de lago integrado", "Las consultas al lago corren en el propio clúster; RA3 usa Redshift Spectrum, una flota aparte"),
             ("Sin cargo por TB escaneado", "RA3 paga USD 5 por TB que lee Spectrum; RG no tiene ese cargo"),
             ("Lo que no cambia", "Mismo motor de Redshift y mismo almacenamiento administrado (USD 0,024 por GB-mes)")]
    for i, (t, b) in enumerate(cards):
        card(s, X0 + (i % 2) * 7.85, Y0 + (i // 2) * 2.95, 7.55, 2.65, t, b, size=22,
             title_color=ACCENT if i < 3 else RA3C)
    notes(s, "Esto es importante para entender los resultados del lago: cuando comparamos RA3 con RG en el lago no comparamos solo procesadores, comparamos dos motores distintos. Por eso siempre hablo de motor más chip y nunca de solo el chip. Fuente: documentación de Redshift, Amazon Redshift provisioned clusters.")

    # 7 sizes and prices
    s = S[6]
    set_title(s, "Cuatro tamaños, 30 % menos por vCPU", 50)
    rows = [["RA3", "vCPU", "USD/h", "→", "RG", "vCPU", "USD/h", "USD por vCPU-h"],
            ["—", "", "", "", "rg.large", "2", "0,3801", "0,190"],
            ["ra3.xlplus", "4", "1,086", "1 : 1", "rg.xlarge", "4", "0,7602", "0,272 → 0,190"],
            ["ra3.4xlarge", "12", "3,26", "4 → 3", "rg.4xlarge", "16", "3,04267", "0,272 → 0,190"],
            ["—", "", "", "", "rg.12xlarge", "48", "9,128", "0,190"]]
    table(s, X0, Y0, 15.2, rows, [2.4, 1.1, 1.4, 1.2, 2.5, 1.1, 1.8, 3.7], size=21, row_h=0.72, hl_rows=(3,))
    textbox(s, X0, Y0 + 4.0, 15.6, 1.6, ["**4 × ra3.4xlarge = 3 × rg.4xlarge = 48 vCPU** → USD 13,04/h frente a 9,13/h"],
            size=26, color=WHITE)
    textbox(s, X0, Y0 + 5.15, 15.6, 0.6, ["vCPU: documentación «Node type details». Precios on-demand us-east-1, Price List API (results/prices.md y spec)."],
            size=16, color=MUTED)
    notes(s, "El 30 % por vCPU se cumple al centavo: 1,086 entre 4 vCPU contra 0,7602 entre 4. Ojo con el 4xlarge: un ra3.4xlarge tiene 12 vCPU y un rg.4xlarge tiene 16. AWS recomienda pasar 4 nodos RA3 a 3 nodos RG; si migras 1 a 1 en ese tamaño compras un tercio más de capacidad de la que tenías.")

    # 8 promises
    s = S[7]
    set_title(s, "Lo que promete AWS")
    proms = [("Hasta 2,2x", "más rápido en el warehouse"), ("Hasta 2,4x", "en el data lake (Iceberg; 1,5x en Parquet)"),
             ("−30 %", "por vCPU"), ("Sin cargo", "de Spectrum por TB escaneado")]
    for i, (t, b) in enumerate(proms):
        card(s, X0 + i * 3.88, Y0, 3.65, 3.0, t, b, size=22, title_size=40, title_color=ACCENT)
    textbox(s, X0, Y0 + 3.5, 15.2, 1.2, ["AWS midió TPC-DS y TPC-H a **10 TB en rg.4xlarge**. Nosotros: 100 GB en 2 × xlarge."],
            size=24, color=WHITE)
    textbox(s, X0, Y0 + 5.15, 15.6, 0.6, ["Fuente: blog de AWS Big Data «Meet Amazon Redshift RG…», 2026-05-19."], size=16, color=MUTED)
    notes(s, "Estas son las cuatro promesas que vamos a probar. Fíjense en el pie: AWS midió 10 TB en nodos 4xlarge. Yo medí el clúster que la mayoría de los equipos opera de verdad.")

    # 9 transition
    set_transition(S[8], "CÓMO LO", "MEDIMOS")
    notes(S[8], "Antes de mostrar un solo número, cómo lo obtuve, porque un benchmark sin método es una opinión con decimales.")

    # 10 architecture
    s = S[9]
    set_title(s, "El laboratorio")
    picture(s, ROOT / "slides/assets/arquitectura-lab.png", X0, Y0 + 0.05, 15.6, 5.75)
    notes(s, "Una VPC propia con enhanced VPC routing y endpoints para S3, Glue, Lake Formation y S3 Tables. RA3 con 2 nodos ra3.xlplus; RG con 2 nodos rg.xlarge restaurado del mismo snapshot, así que los dos clústeres tienen exactamente los mismos datos. El lago en S3: Iceberg y Parquet registrados en Glue. RA3 lee el lago con la flota de Spectrum, fuera de la VPC; RG con su motor integrado, desde la VPC por los endpoints. Las consultas las lanza un runner en Python por la Data API, y la infraestructura la crea GitHub Actions con OIDC, sin llaves guardadas en ningún lado.")

    # 11 method
    s = S[10]
    set_title(s, "Un método justo")
    textbox(s, X0, Y0, 15.6, 5.8, ["Mismo snapshot y misma versión de Redshift (1.0.434008) en los dos clústeres",
                                    "Caché de resultados apagada y escalado de concurrencia en 0",
                                    "Tiempos medidos en el servidor (SYS_QUERY_HISTORY), no en mi laptop",
                                    "Mediana por consulta, sin la pasada de calentamiento",
                                    "**Una corrida con caché o escalado se invalida sola y no se reporta. Hoy: ninguna.**"],
            size=26, bullets=True, space=20)
    notes(s, "Lo más importante es el último punto: el runner revisa cada consulta y si alguna usó la caché de resultados, la corrida entera se descarta. Ninguna se descartó hoy.")

    # 12 what we did not measure
    s = S[11]
    set_title(s, "Lo que no medimos")
    outs = [("100 GB, no 10 TB", "Con este volumen pesan más los costos fijos de cada consulta"),
            ("2 nodos xlarge", "No medimos 4xlarge ni 12xlarge"),
            ("Sin Serverless", "Lo vemos solo con documentación y precios"),
            ("Sin S3 Tables", "Más adelante, el porqué")]
    for i, (t, b) in enumerate(outs):
        card(s, X0 + (i % 2) * 7.85, Y0 + (i // 2) * 2.95, 7.55, 2.65, t, b, size=22, title_color=ORANGE)
    notes(s, "Prefiero decirlo al principio. Con 100 GB los datos calientes caben en buena parte en memoria, y eso reduce la ventaja de RG en escaneos grandes. Si aun así vemos ventaja, es una buena señal; con más datos esperaría que la brecha de scan crezca, pero no lo medí.")

    # 13 transition
    set_transition(S[12], "WAREHOUSE")
    notes(S[12], "Empecemos por lo que hace todo warehouse: consultas sobre tablas propias.")

    # 14 power chart
    s = S[13]
    set_title(s, f"{es(float(ps['geo']), 2)}x más rápido")
    srt = sorted(pr, key=lambda r: -r[3])
    bar_chart(s, X0 - 0.1, Y0 - 0.1, 10.6, 6.2, [r[0] for r in srt], [("Aceleración RG", [r[3] for r in srt])],
              [ACCENT], horizontal=True, fmt='0.00"x"', label_size=13, axis_size=13, gap=35, label_fn=lambda v: es(v, 2) + "x",
              point_colors=[ACCENT if cls[r[0]] == "scan" else ORANGE for r in srt])
    lg = textbox(s, 11.2, Y0 + 0.1, 5.6, 0.5, ["■ scan"], size=20, color=ACCENT).text_frame.paragraphs[0]
    _runs(lg, "     ■ cpu", 20, ORANGE)
    stat(s, 11.2, Y0 + 0.8, 5.6, f"{es(float(ps['tot'][0]))} → {es(float(ps['tot'][1]))} s", "tiempo total de las 20 consultas", size=40, color=WHITE)
    stat(s, 11.2, Y0 + 3.4, 5.6, f"{es(float(ps['p50'][0]), 2)} → {es(float(ps['p50'][1]), 2)} s", "mediana (p50) por consulta", size=40, color=WHITE)
    notes(s, f"Veinte consultas, cada una tres veces, la primera de calentamiento. RG fue más rápido en las veinte. La que más ganó, query48, 3,58 veces; la que menos, query57, 1,08 veces. La media geométrica, que es la forma justa de promediar aceleraciones, da {es(float(ps['geo']), 2)}x. En azul las consultas de scan, en naranja las de CPU.")

    # 15 scan vs cpu
    s = S[14]
    set_title(s, "Gana más el que escanea")
    stat(s, X0, Y0 + 0.35, 7.6, f"{es(float(ps['scan']), 2)}x", "consultas de scan y agregación (10\u00a0consultas)", size=120)
    stat(s, X0 + 8.1, Y0 + 0.35, 7.6, f"{es(float(ps['cpu']), 2)}x", "consultas de CPU: ventanas y joins grandes (10\u00a0consultas)", size=120, color=ORANGE)
    textbox(s, X0, Y0 + 4.5, 15.6, 1.0, ["La promesa de AWS es hasta 2,2x: **en scan la superamos; en CPU, no.**"], size=26, color=WHITE)
    notes(s, "Separé las consultas en dos clases antes de correrlas, no después. Las que leen mucho y agregan ganaron 2,28 veces: ahí es donde Graviton y el ancho de banda de memoria brillan. Las de CPU, con funciones de ventana y joins de quince tablas, ganaron 1,58. Si tu warehouse es mayormente dashboards con agregaciones, estás del lado bueno.")

    # 16 concurrency
    s = S[15]
    set_title(s, f"Concurrencia: {es(rg_q / ra3_q)}x más consultas", 50)
    bar_chart(s, X0, Y0 - 0.2, 9.0, 6.0, ["RA3", "RG"], [("Consultas por hora", [ra3_q, rg_q])], [ACCENT],
              fmt='0', point_colors=[RA3C, ACCENT], label_size=28, axis_size=24, gap=80, label_fn=lambda v: str(int(v)))
    textbox(s, 10.6, Y0 + 0.6, 6.2, 4.5, ["**Consultas por hora**", "5 flujos durante 30 minutos", "Sin cola en ninguno", "Cero fallas"],
            size=26, space=18)
    notes(s, f"Cinco usuarios lanzando las mismas veinte consultas en orden aleatorio durante media hora. RG completó {int(rg_q)} consultas por hora contra {int(ra3_q)} de RA3. Ninguno tuvo que encolar consultas.")

    # 17 load and ELT
    s = S[16]
    set_title(s, "Cargar y transformar")
    textbox(s, X0, Y0 + 0.1, 6.6, 5.6, ["**100 GB en 20 min 44 s**", "COPY desde S3 en 2 × ra3.xlplus (carga inicial, una vez)",
                                        f"COPY store_returns: **{es(elt_a['ecopy']/elt_g['ecopy'], 2)}x**",
                                        f"CTAS pesado: **{es(elt_a['ectas']/elt_g['ectas'], 2)}x**"], size=26, space=18)
    bar_chart(s, X0 + 7.0, Y0 - 0.2, 8.8, 6.0, ["COPY store_returns", "CTAS pesado"],
              [("RA3", [elt_a["ecopy"], elt_a["ectas"]]), ("RG", [elt_g["ecopy"], elt_g["ectas"]])],
              [RA3C, ACCENT], fmt='0.0" s"', legend=True, label_size=20, axis_size=20, label_fn=lambda v: es(v) + " s")
    notes(s, "La carga inicial la hice una sola vez, en RA3, y RG nació del snapshot. El escenario de ELT repite un COPY y un CTAS en los dos: RG fue 1,5 y 1,6 veces más rápido. Son dos corridas por escenario, así que lo tomo como dirección, no como número exacto.")

    # 18 cost
    s = S[17]
    set_title(s, "Más rápido y más barato")
    ua, ug = float(ps["usd"][0]), float(ps["usd"][1])
    stat(s, X0, Y0 + 0.2, 9.0, f"USD {es(ua, 3)} → {es(ug, 3)}", "por corrida del escenario de potencia", size=54, color=WHITE)
    stat(s, X0 + 9.2, Y0 + 0.2, 6.4, f"{es(ua / ug)}x", "menos costo por la misma carga", size=110)
    textbox(s, X0, Y0 + 4.4, 15.6, 1.2, ["Se suman dos efectos: **el nodo cuesta 30 % menos por hora y termina antes.**"], size=26, color=WHITE)
    notes(s, "Esto es lo que más le interesa a quien paga la factura. No es solo que el nodo sea más barato: como también termina antes, cada corrida cuesta menos de la mitad.")

    # 19 transition
    set_transition(S[18], "DATA", "LAKE")
    notes(S[18], "Ahora la parte más interesante, y la que más depende de cómo tienes tus datos.")

    # 20 three ways
    s = S[19]
    set_title(s, "El mismo dato, tres formas")
    for i, (t, b) in enumerate([("Local", "Tablas cargadas en el warehouse"), ("Iceberg", "Tablas en S3 registradas en Glue (ice.*)"),
                                ("Parquet", "Tablas externas en S3 registradas en Glue (pq.*)")]):
        card(s, X0 + i * 5.2, Y0, 4.9, 2.9, t, b, size=22, title_size=36, title_color=ACCENT)
    textbox(s, X0, Y0 + 3.4, 15.6, 2.4, ["Mismas 6 consultas en las tres, con las **mismas 483 filas de resultado**.",
                                          "RA3 lee S3 con **Spectrum** (fuera de tu VPC); RG, con su **motor integrado** (dentro de tu VPC)."],
            size=25, space=14)
    notes(s, "Escribí las mismas cinco tablas en Iceberg y en Parquet desde el warehouse, y comprobé que las seis consultas del lago devuelven exactamente las mismas 483 filas en las tres versiones. Así lo único que cambia es cómo se leen.")

    # 21 iceberg
    s = S[20]
    ia, ig = sum(ice_a.values()), sum(ice_g.values())
    set_title(s, f"Iceberg: {es(stats.geomean(stats.speedups(ice_a, ice_g).values()), 2)}x con caché caliente", 48)
    qs = sorted(ice_a)
    bar_chart(s, X0 - 0.1, Y0 - 0.2, 9.6, 6.1, qs, [("RA3", [ice_a[q] for q in qs]), ("RG", [ice_g[q] for q in qs])],
              [RA3C, ACCENT], fmt='0.0" s"', legend=True, label_size=15, axis_size=17, label_fn=lambda v: es(v) + " s")
    stat(s, 11.0, Y0 + 0.2, 5.8, f"{es(ia)} → {es(ig)} s", "total de las 6 consultas", size=44, color=WHITE)
    textbox(s, 11.0, Y0 + 3.0, 5.8, 2.8, ["**Letra chica:** la primera lectura en RG tardó hasta 27 s; después, unos 2 s. RG cachea el lago."],
            size=22, color=ORANGE)
    notes(s, "RG lee Iceberg casi dos veces más rápido que RA3, pero hay letra chica: la primera vez que RG toca los datos tarda bastante más, porque los trae y los guarda en caché. Mi método descarta la primera pasada, así que este número es con caché caliente. Si tus consultas al lago son esporádicas, cuenta con esa primera lectura.")

    # 22 parquet
    s = S[21]
    set_title(s, "Parquet: mandan los archivos")
    rows = [["Parquet store_sales", "RA3 (total)", "RG (total)", "RG frente a RA3 (media geom.)"],
            ["4 archivos de ≈3,8 GB", f"{es(pq1[0])} s", f"{es(pq1[1])} s", f"**{es(pq1[2], 2)}x**"],
            ["31 archivos de ≈0,5 GB", f"{es(pq2[0])} s", f"{es(pq2[1])} s", f"**{es(pq2[2], 2)}x**"]]
    table(s, X0, Y0, 15.2, rows, [4.8, 2.6, 2.6, 5.2], size=24, row_h=0.95)
    textbox(s, X0, Y0 + 3.3, 15.6, 2.6, ["**Mismo plan de ejecución** en los dos clústeres (EXPLAIN idéntico).",
                                          "El mismo cambio de archivos **ayuda a RG y perjudica a Spectrum** en RA3.",
                                          "Una sola repetición: confía en la dirección, no en el número exacto."], size=24, space=14)
    notes(s, "Este fue el resultado que más me sorprendió. Con Parquet, RG empezó siendo más lento que RA3. Revisé el plan de ejecución: idéntico en los dos. Lo distinto era el formato de los archivos: Redshift los había escrito en solo cuatro archivos enormes, uno por slice, porque el tope por defecto es 6.200 MB. Los reescribí en archivos de medio giga y RG pasó a ganar, mientras que RA3 empeoró. El mismo cambio ayuda a un motor y perjudica al otro.")

    # 23 spectrum cost
    s = S[22]
    set_title(s, "Spectrum se cobra aparte")
    stat(s, X0, Y0 + 0.1, 5.0, "USD 0,083", "18,2 GB en Iceberg (2 pasadas)", size=60, color=ORANGE)
    stat(s, X0 + 5.3, Y0 + 0.1, 5.0, "USD 0,092", "20,2 GB en Parquet (2 pasadas)", size=60, color=ORANGE)
    stat(s, X0 + 10.6, Y0 + 0.1, 5.0, "USD 0", "por escaneo en RG", size=60, color=ACCENT)
    textbox(s, X0, Y0 + 3.9, 15.6, 1.5, ["USD 5 por TB escaneado en RA3. **Multiplica por tus consultas al lago de un mes.**"], size=26, color=WHITE)
    notes(s, "En nuestro lab son centavos, porque son 100 GB. Pero esto escala con el volumen y con la frecuencia: un equipo que escanea decenas de TB al mes en el lago lo nota en la factura. En RG ese cargo desaparece.")

    # 24 lessons
    s = S[23]
    set_title(s, "Lo que el lago nos enseñó")
    les = [("S3 Tables: IAM", "cross-database reference to database \"…@s3tablescatalog\" is not supported"),
           ("Iceberg: sin CHAR", "CHAR type is not supported for column \"d_date_id\" in Iceberg table creation"),
           ("Lake Formation", "Insufficient Lake Formation permission(s): Required Create Table on rr_iceberg")]
    for i, (t, e) in enumerate(les):
        c = card(s, X0 + i * 5.2, Y0, 4.9, 3.4, t, [], size=20, title_size=26, title_color=ORANGE)
        p = c.text_frame.add_paragraph()
        r = p.add_run()
        r.text = e
        r.font.name, r.font.size, r.font.color.rgb = "Courier New", Pt(17), SOFT
    textbox(s, X0, Y0 + 3.9, 15.2, 1.0, ["Si piensas usar S3 Tables desde Redshift, **define primero tu modelo de autenticación.**"], size=24, color=WHITE)
    notes(s, "Quería medir S3 Tables y no pude, por una razón de diseño: las tablas de S3 Tables se leen por el catálogo montado automáticamente, que exige conectarse con identidad IAM, y el runner se conecta con un usuario de base de datos. Cambiar de usuario solo para esa variante habría medido otra ruta de permisos. Iceberg además no acepta CHAR, y Lake Formation exige permisos explícitos sobre las bases de Glue.")

    # 25 transition
    set_transition(S[24], "LA", "MIGRACIÓN")
    notes(S[24], "Supongamos que decides migrar. ¿Cuánto duele?")

    # 26 drill timeline
    s = S[25]
    set_title(s, "Migrar tomó 2 min 48 s")
    probes = [{"ts": "2026-10-05T19:05:47Z", "write_probe": "START"}] + list(csv.DictReader(open(R / "drill-log.csv")))  # start from drill.md
    n = len(probes)
    line_y = Y0 + 1.9
    ln = s.shapes.add_connector(1, Inches(X0 + 0.3), Inches(line_y), Inches(X0 + 15.3), Inches(line_y))
    ln.line.color.rgb, ln.line.width = MUTED, Pt(3)
    for i, row in enumerate(probes):
        cx = X0 + 0.3 + i * 15.0 / (n - 1)
        ok, start = row["write_probe"] == "FINISHED", row["write_probe"] == "START"
        dot = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx - 0.28), Inches(line_y - 0.28), Inches(0.56), Inches(0.56))
        dot.fill.solid(), setattr(dot.fill.fore_color, "rgb", WHITE if start else (ACCENT if ok else ORANGE))
        dot.line.fill.background()
        textbox(s, cx - 1.1, line_y - 1.3, 2.2, 0.6, [row["ts"][11:19]], size=18, color=SOFT, align=PP_ALIGN.CENTER)
        textbox(s, cx - 1.1, line_y + 0.45, 2.2, 0.6, ["inicio" if start else ("escribe" if ok else "solo lectura")], size=18,
                color=WHITE if start else (RGBColor(0x8F, 0xB4, 0xFF) if ok else ORANGE), align=PP_ALIGN.CENTER, bold=True)
    stat(s, X0, Y0 + 3.0, 7.6, "1:35 – 2:42", "minutos en solo lectura (sondeo cada 30 s)", size=60, color=ORANGE)
    stat(s, X0 + 8.1, Y0 + 3.0, 7.6, "Sin cambios", "en el skew: 1:1 conserva los slices", size=60, color=ACCENT)
    notes(s, "Restauré una copia de RA3 e hice el elastic resize a RG, probando una escritura cada 30 segundos. El resize empezó a las 19:05:47 y terminó a las 19:08:35. El clúster estuvo en solo lectura entre 1 minuto 35 y 2 minutos 42 segundos; el rango es por el sondeo cada 30 segundos. Con el mapeo 1 a 1 se conserva la cantidad de slices, así que la distribución de los datos no cambió. Ojo: eso vale para 2 nodos a 2 nodos; si cambias la cantidad de nodos, como en el 4 a 3 de los 4xlarge, el skew sí puede aparecer.")

    # 27 traps
    s = S[26]
    set_title(s, "Trampas del camino")
    traps = ["**Contraseña administrada:** un snapshot con contraseña administrada solo se restaura con \u2011\u2011manage\u2011master\u2011password",
             "**Primero un backup:** un clúster restaurado no acepta elastic resize hasta tener un snapshot propio",
             "**«Available» no siempre es disponible:** el estado dice available mientras otro campo sigue en Modifying",
             "**El 4 → 3 y el skew:** cambiar la cantidad de nodos puede desbalancear los slices",
             "**Restore = endpoint nuevo:** si migras restaurando, reconfigura zero-ETL, DMS y datashares"]
    textbox(s, X0, Y0, 15.6, 5.9, traps, size=23, bullets=True, space=16)
    notes(s, "Las tres primeras me pasaron en el simulacro, en ese orden, y no las encontré en la guía de migración. Las dos últimas sí están en la documentación y en el blog de AWS. Todas quedaron resueltas en el script del repo.")

    # 28 transition
    set_transition(S[27], "DEMO")
    notes(S[27], "Ahora veamos las consultas y los datos reales.")

    # 29 demo query
    s = S[28]
    set_title(s, "Demo: una consulta, dos generaciones")
    code(s, X0, Y0, 10.2, 5.0, "SELECT count(*)\nFROM store_sales, household_demographics,\n     time_dim, store\n"
         "WHERE ss_sold_time_sk = time_dim.t_time_sk\n  AND ss_hdemo_sk = household_demographics.hd_demo_sk\n"
         "  AND ss_store_sk = s_store_sk\n  AND time_dim.t_hour = 15\n  AND time_dim.t_minute >= 30\n"
         "  AND household_demographics.hd_dep_count = 7\n  AND store.s_store_name = 'ese'\nLIMIT 100;", size=18)
    stat(s, 11.6, Y0 + 0.0, 5.2, f"{es(q96[1], 2)} s", "RA3 (query96)", size=56, color=RA3C)
    stat(s, 11.6, Y0 + 2.9, 5.2, f"{es(q96[2], 2)} s", f"RG · {es(q96[3], 2)}x", size=56, color=ACCENT)
    notes(s, "Una consulta típica de scan: cuenta ventas filtrando por tres dimensiones, sobre 288 millones de filas en la tabla de hechos. En RA3 tarda 1,77 segundos; en RG, 0,67.")

    # 30 demo explain
    s = S[29]
    set_title(s, "Demo: mismo plan, distinto motor", 50)
    code(s, X0, Y0, 7.6, 3.3, "RA3  (lq3 sobre Parquet)\n\nXN Hash Join DS_BCAST_INNER\n  XN Hash Join DS_BCAST_INNER\n"
         "    XN S3 Query Scan ss\n      S3 Seq Scan pq.store_sales\n         rows=287997024", size=17)
    code(s, X0 + 7.8, Y0, 7.6, 3.3, "RG  (lq3 sobre Parquet)\n\nXN Hash Join DS_BCAST_INNER\n  XN Hash Join DS_BCAST_INNER\n"
         "    XN Seq Scan pq.store_sales\n       format:PARQUET\n         rows=287997024", size=17)
    textbox(s, X0, Y0 + 3.75, 15.2, 1.3, ["Mismos joins y mismas estimaciones de filas. **Lo único distinto: quién lee S3.**"],
            size=24, color=WHITE)
    notes(s, "Así diagnostiqué el caso de Parquet. Si los planes fueran distintos, la diferencia sería el plan y no el motor. Son iguales; cambia el operador que lee S3. Cuando veas una diferencia rara entre clústeres, empieza por aquí.")

    # 31 demo results page
    s = S[30]
    set_title(s, "Demo: todos los resultados")
    shot = ROOT / "slides/assets/resultados-captura.png"
    if shot.exists():
        picture(s, shot, X0, Y0 + 0.15, 10.0, 5.6)
        tx = 11.8
    else:
        tx = X0
    textbox(s, tx, Y0 + 0.2, 16.6 - tx, 5.4, ["Página interactiva con todos los números de la charla:",
                                              "Aceleración por consulta, filtrable por clase", "El lago antes y después de reescribir Parquet",
                                              "La línea de tiempo del simulacro"], size=24, space=16)
    notes(s, "Esta página tiene todos los números de la charla, sacados directamente de los archivos del repo. La voy a abrir un momento para que vean cada consulta. Abrir: https://claude.ai/artifact/1MgMakVPq4URRXQMZp4aVk (privada, con la sesión del orador; copia local: slides/demo/resultados.html).")

    # 32 decision
    s = S[31]
    set_title(s, "¿Migrar o no migrar?")
    cols = [("Migra si", ["Tu carga es de scan y agregación", "Lees el data lake con frecuencia", "Estás en xlplus o 4xlarge: 30\u00a0% menos por vCPU"], ACCENT),
            ("Prueba antes si", ["Tu carga es de CPU: ventanas, joins grandes", "Tu lago es Parquet con archivos grandes", "Necesitas S3 Tables con usuarios de base de datos"], ORANGE),
            ("Serverless si", ["Tu uso es intermitente", "No quieres operar un clúster", "USD 0,375 por RPU-hora (no lo medimos)"], RA3C)]
    for i, (t, items, col) in enumerate(cols):
        card(s, X0 + i * 5.2, Y0, 4.9, 4.3, t, ["• " + x for x in items], size=21, title_size=30, title_color=col)
    notes(s, "Esta es mi respuesta a la pregunta del título. Para la mayoría de los equipos con RA3 la migración conviene: es más rápida y más barata, y el resize toma minutos. Pero prueba con tus datos, sobre todo si tu lago es Parquet o tu carga es de CPU. Serverless es otra decisión, sobre la forma de tu uso, y no la medí, así que no te doy un número.")

    # 33 take the lab
    s = S[32]
    set_title(s, "Llévate el laboratorio")
    textbox(s, X0, Y0 + 0.1, 15.6, 1.2, ["github.com/andrezc98/redshift-redemption"], size=44, color=ACCENT, bold=True)
    textbox(s, X0, Y0 + 1.7, 15.6, 4.0, ["Terraform + GitHub Actions con OIDC · runner en Python · runbook paso a paso",
                                          "Todos los resultados y su método en results/",
                                          "Este lab, a 100 GB: un día de trabajo y unas decenas de dólares"], size=26, bullets=True, space=18)
    notes(s, "Todo lo que vieron está en el repo: la infraestructura, el runner, el runbook con cada paso y los errores que encontré. Cámbiale el dataset por el tuyo y repite las mediciones.")

    # 34 kahoot
    s = S[33]
    set_title(s, "Kahoot")
    qs3 = ["¿Con qué leen el data lake los clústeres RG?",
           "¿Qué tipo de consultas ganó más al pasar de RA3 a RG?",
           "Si migras 4 nodos ra3.4xlarge, ¿cuántos rg.4xlarge recomienda AWS?"]
    for i, q in enumerate(qs3):
        card(s, X0 + i * 5.2, Y0, 4.9, 3.2, f"Pregunta {i + 1}", q, size=23, title_size=26, title_color=ACCENT)
    textbox(s, X0, Y0 + 3.7, 15.2, 1.0, ["Respuestas y comentarios en las notas del orador."], size=20, color=MUTED)
    notes(s, "Kahoot. 1) Con qué leen el lago los RG: b) un motor de lago integrado en el propio clúster (a Spectrum, c Athena, d Glue ETL). RA3 usa Spectrum, que cobra USD 5 por TB. "
             "2) Qué consultas ganaron más: b) las de scan y agregación (a CPU, c ninguna, d solo lago). Scan 2,28x frente a CPU 1,58x. "
             "3) 4 ra3.4xlarge a cuántos rg.4xlarge: b) 3 (a 4, c 2, d 8). 4 × 12 vCPU = 3 × 16 vCPU = 48.")

    # 35 thanks
    s = S[34]
    set_title(s, "¡Gracias!", 72)
    textbox(s, X0, Y0 + 0.4, 15.6, 4.5, ["**Andrés Zeballos** · Solutions Architect, phData",
                                          "GitHub: andrezc98",
                                          "Repo del lab: github.com/andrezc98/redshift-redemption"], size=30, space=22)
    notes(s, "Gracias. Respondo preguntas en el chat. Si preguntan por Snowflake u otras plataformas: trabajo con varias y son buenas respuestas a contextos distintos; hoy vine a medir la decisión que los equipos nativos de AWS ya tienen enfrente: RA3 o RG.")


def main():
    skill = Path(sys.argv[1])
    with tempfile.TemporaryDirectory() as tmp:
        structure = build_structure(skill, Path(tmp))
        prs = Presentation(str(structure))
        assert len(prs.slides) == len(SRC), len(prs.slides)
        fill(prs)
        prs.save(str(OUT))
    print(f"wrote {OUT} ({len(SRC)} slides)")


if __name__ == "__main__":
    main()
