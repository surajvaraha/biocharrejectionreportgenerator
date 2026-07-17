import pandas as pd
import requests
import concurrent.futures
import time

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Image as RLImage,
    Spacer, PageBreak, KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
import os
import datetime
import re

# ==========================================
# CONFIGURATION
# ==========================================
OUTPUT_DIR = "generated_reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Varaha brand palette (see varaha-brand-guidelines) ---
TEAL       = colors.HexColor("#07342f")
TEAL_LIGHT = colors.HexColor("#0a4f47")
TEAL_MID   = colors.HexColor("#3d6a64")
AMBER      = colors.HexColor("#f9ac00")
SAGE       = colors.HexColor("#dfedee")
SAGE_DARK  = colors.HexColor("#c5dfe0")
TEXT       = colors.HexColor("#545454")
TEXT_LIGHT = colors.HexColor("#777777")
BORDER     = colors.HexColor("#e0e0e0")
REJECT_RED = colors.HexColor("#c0392b")
WHITE      = colors.white

# --- Human labels + display order for stage codes coming from the DB ---
STAGE_LABELS = {
    "ArtisanalProcessMoisture":       "Wood Moisture",
    "ArtisanalProcessPreStart":       "Pre-Start",
    "ArtisanalProcessStart":          "Process Start",
    "ArtisanalProcessMiddle":         "Process Middle",
    "ArtisanalProcessEnd":            "Process End",
    "ArtisanalProcessPostQuenching":  "Post-Quenching",
    "ArtisanalProcessQuenchingVideo": "Quenching Video",
    "ArtisanalProcessBiocharSampling": "Biochar Sampling",
}
STAGE_ORDER = {code: i for i, code in enumerate([
    "ArtisanalProcessMoisture", "ArtisanalProcessPreStart", "ArtisanalProcessStart",
    "ArtisanalProcessMiddle", "ArtisanalProcessEnd", "ArtisanalProcessPostQuenching",
    "ArtisanalProcessQuenchingVideo", "ArtisanalProcessBiocharSampling",
])}


# ==========================================
# FONTS — use Inter if bundled in ./fonts, else fall back to Helvetica
# ==========================================
def _register_fonts():
    font_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    candidates = {
        "Inter":      "Inter-Regular.ttf",
        "Inter-Bold": "Inter-Bold.ttf",
        "Inter-Semi": "Inter-SemiBold.ttf",
    }
    try:
        if all(os.path.exists(os.path.join(font_dir, f)) for f in candidates.values()):
            pdfmetrics.registerFont(TTFont("Inter", os.path.join(font_dir, candidates["Inter"])))
            pdfmetrics.registerFont(TTFont("Inter-Bold", os.path.join(font_dir, candidates["Inter-Bold"])))
            pdfmetrics.registerFont(TTFont("Inter-Semi", os.path.join(font_dir, candidates["Inter-Semi"])))
            return "Inter", "Inter-Bold", "Inter-Semi"
    except Exception as e:
        print(f"Font registration failed, falling back to Helvetica: {e}")
    return "Helvetica", "Helvetica-Bold", "Helvetica-Bold"

FONT, FONT_BOLD, FONT_SEMI = _register_fonts()


# ==========================================
# PARTNER NAME RESOLUTION
# The partner name is provided by the Superset export as a `partner_name` column
# (Superset joins charify's facilities.organization_id to the org directory). The
# tool never touches a database — it just reads what's in the sheet, with sensible
# fallbacks if the column is missing/blank.
# ==========================================
def resolve_partner_name(partner_from_sheet, org_id, facility_name):
    p = clean_str(partner_from_sheet)
    if p:
        return p
    f = clean_str(facility_name)
    if f:
        return f
    key = clean_str(org_id)
    return f"Organization {key}" if key else "Unknown Partner"


# ==========================================
# COLUMN MATCHING (tolerant to spacing/casing in the export)
# ==========================================
def normalize_name(name):
    if not isinstance(name, str):
        return ""
    return re.sub(r"[^a-zA-Z0-9]", "", name).lower()

def make_getter(df):
    cols_map = {normalize_name(c): c for c in df.columns}
    def get(row, *names, default=""):
        for n in names:
            actual = cols_map.get(normalize_name(n))
            if actual is not None:
                val = row.get(actual, default)
                if pd.isna(val):
                    return default
                return val
        return default
    return get


# ==========================================
# DATE / VALUE FORMATTING
# ==========================================
def fmt_dt(val, with_time=True):
    """Format dates that may arrive as datetime, pandas Timestamp, epoch, or string."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    if isinstance(val, str):
        s = val.strip()
        if s.lower() in ("", "nan", "none", "nat"):
            return ""
        # Try to parse ISO-ish strings for consistent formatting; else return as-is.
        try:
            dt = pd.to_datetime(s)
            return dt.strftime("%d %b %Y %H:%M" if with_time else "%d %b %Y")
        except Exception:
            return s
    # numeric epoch (seconds)
    if isinstance(val, (int, float)):
        try:
            dt = datetime.datetime.utcfromtimestamp(float(val))
            return dt.strftime("%d %b %Y %H:%M" if with_time else "%d %b %Y")
        except Exception:
            return str(val)
    # datetime / Timestamp
    try:
        return pd.to_datetime(val).strftime("%d %b %Y %H:%M" if with_time else "%d %b %Y")
    except Exception:
        return str(val)

def clean_str(val, default=""):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    s = str(val).strip()
    return default if s.lower() in ("nan", "none", "") else s


# ==========================================
# IMAGE DOWNLOADER
# ==========================================
def download_image(url):
    try:
        if not isinstance(url, str) or not url.startswith("http"):
            return None
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200 and resp.content:
            return BytesIO(resp.content)
    except Exception as e:
        print(f"Error downloading image {url}: {e}")
    return None


# ==========================================
# PDF GENERATOR (Varaha branded)
# ==========================================
def _page_furniture(canvas, doc):
    """Header band + footer drawn on every page."""
    w, h = A4
    canvas.saveState()
    # Header band
    band_h = 46
    canvas.setFillColor(TEAL)
    canvas.rect(0, h - band_h, w, band_h, fill=1, stroke=0)
    # Amber accent line under the band
    canvas.setFillColor(AMBER)
    canvas.rect(0, h - band_h - 3, w, 3, fill=1, stroke=0)
    # Wordmark + title
    canvas.setFillColor(WHITE)
    canvas.setFont(FONT_BOLD, 16)
    canvas.drawString(30, h - 30, "VARAHA")
    canvas.setFont(FONT, 10)
    canvas.setFillColor(SAGE)
    canvas.drawRightString(w - 30, h - 29, "Biochar Rejection Report")
    # Footer
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(30, 28, w - 30, 28)
    canvas.setFont(FONT, 7.5)
    canvas.setFillColor(TEXT_LIGHT)
    gen = datetime.datetime.now().strftime("%d %b %Y %H:%M")
    canvas.drawString(30, 18, f"Generated {gen}  ·  Varaha · Confidential")
    canvas.drawRightString(w - 30, 18, f"Page {doc.page}")
    canvas.restoreState()


def create_partner_pdf(partner_name, batches, output_filename, progress_callback=None):
    """Generate a Varaha-branded PDF for one partner containing all rejected batches.
       Each batch begins on its own page; its rejected images flow in a 2-column grid
       and continue across pages as needed (handles 9+ images per batch)."""

    top_margin = 62  # clear the header band
    doc = SimpleDocTemplate(
        output_filename, pagesize=A4,
        rightMargin=30, leftMargin=30, topMargin=top_margin, bottomMargin=40,
        title=f"Varaha Biochar Rejection Report - {partner_name}",
        author="Varaha",
    )
    styles = getSampleStyleSheet()
    st_title  = ParagraphStyle("VTitle", parent=styles["Normal"], fontName=FONT_BOLD,
                               fontSize=18, textColor=TEAL, leading=22, spaceAfter=2)
    st_sub    = ParagraphStyle("VSub", parent=styles["Normal"], fontName=FONT,
                               fontSize=9.5, textColor=TEXT_LIGHT, leading=13)
    st_lbl    = ParagraphStyle("VLbl", parent=styles["Normal"], fontName=FONT_SEMI,
                               fontSize=8, textColor=TEAL, leading=11)
    st_val    = ParagraphStyle("VVal", parent=styles["Normal"], fontName=FONT,
                               fontSize=9, textColor=TEXT, leading=12)
    st_stage  = ParagraphStyle("VStage", parent=styles["Normal"], fontName=FONT_SEMI,
                               fontSize=8.5, textColor=WHITE, alignment=TA_CENTER, leading=12)
    st_reason = ParagraphStyle("VReason", parent=styles["Normal"], fontName=FONT,
                               fontSize=8.5, textColor=REJECT_RED, alignment=TA_CENTER, leading=11)
    st_noimg  = ParagraphStyle("VNoImg", parent=styles["Normal"], fontName=FONT,
                               fontSize=8.5, textColor=TEXT_LIGHT, alignment=TA_CENTER, leading=11)
    st_batch  = ParagraphStyle("VBatch", parent=styles["Normal"], fontName=FONT_BOLD,
                               fontSize=11, textColor=WHITE, leading=14)

    # --- Pre-download all images for this partner in parallel ---
    all_urls = set()
    for batch in batches:
        for item in batch["images"]:
            u = item.get("image")
            if isinstance(u, str) and u.startswith("http"):
                all_urls.add(u)
    image_map = {}
    if all_urls:
        total = len(all_urls)
        done = 0
        if progress_callback:
            progress_callback(f"Downloading {total} images for {partner_name}...", percent=None)
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            fut = {ex.submit(download_image, u): u for u in all_urls}
            for f in concurrent.futures.as_completed(fut):
                done += 1
                if progress_callback and done % 5 == 0:
                    progress_callback(f"Downloading images for {partner_name} ({done}/{total})...", percent=None)
                data = f.result()
                if data:
                    image_map[fut[f]] = data

    elements = []

    # --- Cover strip: partner + totals ---
    total_batches = len(batches)
    total_images = sum(len(b["images"]) for b in batches)
    elements.append(Paragraph(partner_name, st_title))
    elements.append(Paragraph(
        f"{total_batches} rejected batch{'es' if total_batches != 1 else ''} · "
        f"{total_images} flagged image{'s' if total_images != 1 else ''}", st_sub))
    elements.append(Spacer(1, 10))

    def info_card(meta):
        def cell(lbl, val):
            return [Paragraph(lbl, st_lbl), Paragraph(clean_str(val) or "—", st_val)]
        data = [
            cell("PARTNER", meta.get("partner")) + cell("BATCH ID", meta.get("batch_id")),
            cell("FACILITY", meta.get("facility")) + cell("KILN", meta.get("kiln")),
            cell("PRODUCTION DATE", meta.get("production")) + cell("VALIDATED", meta.get("validated")),
        ]
        # Task columns only come from the optional second upload — omit the row entirely
        # when none of the three were populated, rather than show an all-dash row.
        if meta.get("task_status") or meta.get("task_created") or meta.get("task_due"):
            data.append(cell("TASK CREATED", meta.get("task_created")) + cell("TASK DUE", meta.get("task_due")))
        t = Table(data, colWidths=[1.0*inch, 2.3*inch, 1.0*inch, 2.4*inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), SAGE),
            ("LINEBELOW", (0, 0), (-1, -2), 0.4, SAGE_DARK),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("LINEBEFORE", (0, 0), (0, -1), 3, AMBER),
        ]))
        return t

    def image_cell(item):
        url = item.get("image")
        if url in image_map:
            img = RLImage(BytesIO(image_map[url].getvalue()), width=2.9*inch, height=2.1*inch, kind="proportional")
            img.hAlign = "CENTER"
            img_flow = img
        elif not url:
            img_flow = Paragraph("[No image link]", st_noimg)
        else:
            img_flow = Paragraph("[Image unavailable]", st_noimg)

        stage_lbl = item.get("stage", "")
        reason = clean_str(item.get("reason"), "No reason recorded")

        stage_tbl = Table([[Paragraph(stage_lbl.upper(), st_stage)]], colWidths=[2.95*inch])
        stage_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), TEAL),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))

        cell = Table([[img_flow], [stage_tbl], [Paragraph(reason, st_reason)]], colWidths=[3.05*inch])
        cell.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.75, BORDER),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
            ("TOPPADDING", (0, 2), (-1, 2), 4),
        ]))
        return cell

    first = True
    for batch in batches:
        if not first:
            elements.append(PageBreak())
        first = False

        meta = batch["meta"]
        # Batch banner
        banner = Table([[Paragraph(f"Batch / Kiln ID: {clean_str(meta.get('batch_id')) or '—'}", st_batch)]],
                       colWidths=[doc.width])
        banner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), TEAL_MID),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(KeepTogether([banner, Spacer(1, 4), info_card(meta)]))
        elements.append(Spacer(1, 10))

        items = batch["images"]
        if not items:
            elements.append(Paragraph("This batch is marked rejected but has no flagged images.", st_val))
            continue

        for i in range(0, len(items), 2):
            pair = items[i:i + 2]
            cells = [image_cell(it) for it in pair]
            if len(cells) < 2:
                cells.append(Spacer(1, 1))
            row = Table([cells], colWidths=[3.4*inch, 3.4*inch])
            row.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]))
            elements.append(row)

    try:
        doc.build(elements, onFirstPage=_page_furniture, onLaterPages=_page_furniture)
        print(f"Successfully created: {output_filename}")
        return output_filename
    except Exception as e:
        print(f"Failed to build PDF {output_filename}: {e}")
        return None


# ==========================================
# VALIDATION TASKS (optional second sheet)
# Superset exports this separately from the rejection rows (superset_task_query.sql)
# because the task table lives in a different database (MasterService/Regen) with no
# cross-database join available — see superset_rejection_query.sql for why. Keyed on
# batch_kiln_id = ref_id.
# ==========================================
def load_task_lookup(tasks_file_path):
    """Build {batch_kiln_id_str: {task_status, task_created, task_due}} from the
       optional Validation Tasks export. Returns {} if no file was given."""
    if not tasks_file_path:
        return {}
    try:
        if tasks_file_path.endswith(".csv"):
            tdf = pd.read_csv(tasks_file_path)
        else:
            tdf = pd.read_excel(tasks_file_path)
    except Exception as e:
        print(f"Failed to read tasks file, continuing without task data: {e}")
        return {}

    tget = make_getter(tdf)
    lookup = {}
    for _, trow in tdf.iterrows():
        batch_id = clean_str(tget(trow, "batch_kiln_id", "ref_id", "batch_id"))
        if not batch_id:
            continue
        lookup[batch_id] = {
            "task_status": clean_str(tget(trow, "task_status", "status")),
            "task_created": fmt_dt(tget(trow, "task_created_at", "created_on", "created_at"), with_time=True),
            "task_due": fmt_dt(tget(trow, "task_due_date", "due_date"), with_time=False),
        }
    return lookup


# ==========================================
# MAIN LOGIC
# ==========================================
def process_data_and_generate_reports(file_path, progress_callback=None, tasks_file_path=None):
    print(f"Reading data from {file_path}...")
    if progress_callback:
        progress_callback("Reading data...")

    try:
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
    except Exception as e:
        return False, f"Failed to read file: {str(e)}", []

    if df.empty:
        return True, "The uploaded file has no rows.", []

    get = make_getter(df)
    task_lookup = load_task_lookup(tasks_file_path)

    # partner_key -> {"name": str, "batches": {batch_id: {"meta": {...}, "images": [...]}}}
    partners = {}
    errors = 0

    if progress_callback:
        progress_callback(f"Processing {len(df)} rows...")

    for index, row in df.iterrows():
        try:
            org_id = clean_str(get(row, "organization_id", "org_id"))
            facility = clean_str(get(row, "facility_name", "facility"))
            batch_id = clean_str(get(row, "batch_kiln_id", "batch_id", "batch kiln id"))

            if not batch_id:
                continue  # a report row must belong to a batch

            partner_sheet = clean_str(get(row, "partner_name", "organization_name", "org_name", "partner"))
            partner_name = resolve_partner_name(partner_sheet, org_id, facility)
            partner_key = partner_name

            stage_code = clean_str(get(row, "stage_code", "ref_sub_type"))
            stage_label = clean_str(get(row, "stage")) or STAGE_LABELS.get(stage_code, stage_code or "Stage")

            image_url = clean_str(get(row, "image_url", "image", "media_url"))
            reason = clean_str(get(row, "rejection_reason", "reason", "verification_remarks"))

            if partner_key not in partners:
                partners[partner_key] = {"name": partner_name, "batches": {}}

            batches = partners[partner_key]["batches"]
            if batch_id not in batches:
                task_meta = task_lookup.get(batch_id, {})
                batches[batch_id] = {
                    "meta": {
                        "partner": partner_name,
                        "facility": facility,
                        "batch_id": batch_id,
                        "kiln": clean_str(get(row, "kiln_name", "kiln")),
                        "production": fmt_dt(get(row, "production_start", "production_date"), with_time=False),
                        "validated": fmt_dt(get(row, "validated_at", "last_verified_at"), with_time=True),
                        "status": clean_str(get(row, "batch_status", "status")),
                        "task_status": task_meta.get("task_status", ""),
                        "task_created": task_meta.get("task_created", ""),
                        "task_due": task_meta.get("task_due", ""),
                    },
                    "_sort_seen": {},
                    "images": [],
                }
            batches[batch_id]["images"].append({
                "stage": stage_label,
                "stage_code": stage_code,
                "image": image_url,
                "reason": reason,
            })
        except Exception as row_error:
            errors += 1
            print(f"Error processing row {index}: {row_error}")
            continue

    # Sort each batch's images by stage order, then flatten to the structure the PDF wants.
    partner_payloads = {}
    for pkey, pdata in partners.items():
        batch_list = []
        for bid, b in pdata["batches"].items():
            b["images"].sort(key=lambda it: (STAGE_ORDER.get(it.get("stage_code"), 99), it.get("stage", "")))
            batch_list.append({"meta": b["meta"], "images": b["images"]})
        # Batches ordered by production date desc-ish (fall back to id)
        batch_list.sort(key=lambda x: str(x["meta"].get("batch_id")))
        partner_payloads[pdata["name"]] = batch_list

    total_partners = len(partner_payloads)
    print(f"Found {total_partners} partners with rejections "
          f"(rows: {len(df)}, row errors: {errors}).")
    if total_partners == 0:
        return True, "No rejection rows found in the file.", []

    if progress_callback:
        progress_callback(f"Found {total_partners} partners. Generating PDFs...", percent=5)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    generated = []
    completed = 0
    start = time.time()

    def build_one(item):
        name, batch_list = item
        safe = "".join(c if c.isalnum() else "_" for c in name)[:80]
        fpath = os.path.join(OUTPUT_DIR, f"Report_{safe}.pdf")
        cb = progress_callback if total_partners < 3 else None
        try:
            return create_partner_pdf(name, batch_list, fpath, progress_callback=cb)
        except Exception as e:
            print(f"Error generating PDF for {name}: {e}")
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(build_one, it): it for it in partner_payloads.items()}
        for f in concurrent.futures.as_completed(futures):
            completed += 1
            res = f.result()
            if res:
                generated.append(res)
            percent = 5 + int((completed / total_partners) * 90)
            elapsed = time.time() - start
            eta = (total_partners - completed) * (elapsed / completed) if completed else 0
            eta_str = f"{int(eta)}s" if eta < 60 else f"{int(eta // 60)}m {int(eta % 60)}s"
            msg = f"Generated {completed}/{total_partners} reports"
            print(f"{msg}... ETA: {eta_str}")
            if progress_callback:
                progress_callback(msg, percent=percent, eta=eta_str)

    if generated:
        return True, "Reports generated successfully.", generated
    return True, "No reports were generated.", []


if __name__ == "__main__":
    pass
