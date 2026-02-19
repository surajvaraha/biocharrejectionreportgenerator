import pandas as pd
import requests
import concurrent.futures
import time

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image as RLImage, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO
import os
import json
import traceback
import re

# ==========================================
# CONFIGURATION
# ==========================================
OUTPUT_DIR = "generated_reports"

# Create output directory if it doesn't exist
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

SHEET_CONFIG = {
    'meta_map': {
        'partner': 'Partner Name',
        'inventoryId': 'Batch Kiln ID',
        'date': 'Production_Start_Date',
        'time': 'Production_Time_Date',
        'kilnId': 'Kiln ID',
        'artisan': 'Kiln Name',
        'slot': 'Facility Name'
    },
    'checks': [
        ('Wood_Moisture.1', 'No', 'Wood Moisture 1', 'Wood Moisture Image 1', 'Moisture is within limit'),
        ('Wood_Moisture.2', 'No', 'Wood Moisture 2', 'Wood Moisture Image 2', 'Moisture is within limit.1'),
        ('Wood_Moisture.3', 'No', 'Wood Moisture 3', 'Wood Moisture Image 3', 'Moisture is within limit.2'),
        ('Wood_Moisture.4', 'No', 'Wood Moisture 4', 'Wood Moisture Image 4', 'Moisture is within limit.3'),
        ('Wood_Moisture.5', 'No', 'Wood Moisture 5', 'Wood Moisture Image 5', 'Moisture is within limit.4'),
        ('1.Process Start (Image)_Status', 'Rejected', 'Process Start', 'Process Start (Image)', '1.Process Start (Image)_Status Remark'),
        ('2.Process Middle (Image)_Status', 'Rejected', 'Process Middle', 'Process Middle (Image)', '2.Process Middle (Image)_Status Remark'),
        ('3.90%  (Image)_Status', 'Rejected', '90% End', '90% Done (Image)', '3.90% (Image)_Status Remark'),
        ('4.Process End (Image)_Status', 'Rejected', 'Process End', 'Process End (Image)', '4.Process End (Image)_Status Remark')
    ]
}

# ==========================================
# 1. IMAGE DOWNLOADER
# ==========================================
def download_image(url):
    """Downloads an image from a URL and returns it as a BytesIO object for ReportLab."""
    try:
        if not isinstance(url, str) or not url.startswith('http'):
            return None
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            img_data = BytesIO(response.content)
            return img_data
    except Exception as e:
        print(f"Error downloading image {url}: {e}")
    return None

# ==========================================
# 2. PDF GENERATOR
# ==========================================
def create_partner_pdf(partner_name, batches, output_filename, progress_callback=None):
    """Generates a PDF for a specific partner containing all their rejected batches.
       Downloads all images in parallel first to speed up generation."""
    
    doc = SimpleDocTemplate(output_filename, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom Styles
    style_header_text = ParagraphStyle('HeaderVal', parent=styles['Normal'], fontSize=9, leading=11)
    style_header_lbl = ParagraphStyle('HeaderLbl', parent=styles['Normal'], fontSize=9, leading=11, fontName='Helvetica-Bold')
    style_reason = ParagraphStyle('Reason', parent=styles['Normal'], textColor=colors.red, fontSize=10, leading=12)
    style_stage = ParagraphStyle('Stage', parent=styles['Normal'], textColor=colors.white, backColor=colors.darkgrey, fontSize=8, alignment=1, spaceBefore=4)

    # --- 1. PRE-DOWNLOAD IMAGES IN PARALLEL ---
    # Collect all unique image URLs for this partner
    all_image_urls = set()
    for batch in batches:
        for item in batch['images']:
            if item['image'] and isinstance(item['image'], str) and item['image'].startswith('http'):
                all_image_urls.add(item['image'])
    
    image_map = {}
    if all_image_urls:
        total_imgs = len(all_image_urls)
        downloaded = 0
        if progress_callback:
            progress_callback(f"Downloading {total_imgs} validation images for {partner_name}...", percent=None)

        # Use a ThreadPool to download images concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {executor.submit(download_image, url): url for url in all_image_urls}
            for future in concurrent.futures.as_completed(future_to_url):
                downloaded += 1
                if progress_callback and downloaded % 5 == 0:
                     progress_callback(f"Downloading images for {partner_name} ({downloaded}/{total_imgs})...", percent=None)
                
                url = future_to_url[future]
                try:
                    data = future.result()
                    if data:
                        image_map[url] = data
                except Exception as e:
                    print(f"Failed to download {url}: {e}")

    def build_header(meta):
        header_data = [
            [Paragraph('Partner Name:', style_header_lbl), Paragraph(str(meta.get('partner', '')), style_header_text),
             Paragraph('Inventory/Batch ID:', style_header_lbl), Paragraph(str(meta.get('inventoryId', '')), style_header_text)],
            [Paragraph('Date / Time:', style_header_lbl), Paragraph(f"{meta.get('date', '')} {meta.get('time', '')}", style_header_text),
             Paragraph('Kiln ID:', style_header_lbl), Paragraph(str(meta.get('kilnId', '')), style_header_text)],
            [Paragraph('Artisan/Name:', style_header_lbl), Paragraph(str(meta.get('artisan', '')), style_header_text),
             Paragraph('Slot/Facility:', style_header_lbl), Paragraph(str(meta.get('slot', '')), style_header_text)],
        ]
        t_header = Table(header_data, colWidths=[1.2*inch, 2.5*inch, 1.2*inch, 2.0*inch])
        t_header.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        return t_header

    def build_image_cell(item):
        img_url = item['image']
        if img_url in image_map:
            img_data = BytesIO(image_map[img_url].getvalue())
            img_flowable = RLImage(img_data, width=3*inch, height=2.2*inch)
            img_flowable.hAlign = 'CENTER'
        elif not img_url:
            img_flowable = Paragraph("[No Image Link]", styles['Normal'])
        else:
            img_flowable = Paragraph("[Image Download Failed]", styles['Normal'])

        stage_para = Paragraph(f"STAGE: {item['stage']}", style_stage)
        reason_text = item.get('reason', '')
        reason_para = Paragraph(f"Reason: {reason_text}", style_reason) if reason_text else Spacer(1, 1)

        cell_table = Table([[img_flowable], [stage_para], [reason_para]], colWidths=[3.1*inch])
        cell_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        return cell_table

    def build_image_row(pair):
        """Build a single 2-column row table from 1 or 2 rejection items."""
        row_cells = [build_image_cell(item) for item in pair]
        if len(row_cells) < 2:
            row_cells.append(Spacer(1, 1))

        t_row = Table([row_cells], colWidths=[3.4*inch, 3.4*inch])
        t_row.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
        ]))
        return t_row

    # --- 2. BUILD PDF ---
    first_page = True

    for batch in batches:
        meta = batch['meta']
        rejection_items = batch['images']

        if not first_page:
            elements.append(PageBreak())
        first_page = False

        elements.append(Paragraph("Rejection Report", styles['Heading2']))
        elements.append(build_header(meta))
        elements.append(Spacer(1, 0.2*inch))

        if not rejection_items:
            elements.append(Paragraph("This batch has rejections marked but no images were found.", styles['Normal']))
            continue

        for i in range(0, len(rejection_items), 2):
            pair = rejection_items[i:i+2]
            elements.append(build_image_row(pair))
            
    try:
        doc.build(elements)
        print(f"Successfully created: {output_filename}")
        return output_filename
    except Exception as e:
        print(f"Failed to build PDF {output_filename}: {e}")
        return None


# ==========================================
# 4. MAIN LOGIC
# ==========================================

def normalize_name(name):
    """Normalize string for robust column matching."""
    if not isinstance(name, str): return ""
    # Remove all whitespace and non-alphanumeric, lowercase
    return re.sub(r'[^a-zA-Z0-9]', '', name).lower()

def safe_get(row, col_name, df_cols_map):
    """Finds a column in the row using normalized name matching."""
    norm_target = normalize_name(col_name)
    actual_col = df_cols_map.get(norm_target)
    if actual_col:
        return row.get(actual_col, '')
    return ''

def process_data_and_generate_reports(file_path, progress_callback=None):
    config = SHEET_CONFIG
    
    print(f"Reading data from {file_path}...")
    if progress_callback: progress_callback("Reading data...")

    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
    except Exception as e:
        return False, f"Failed to read file: {str(e)}", []

    # Basic cleanup
    df = df.fillna('')
    
    # Create a mapping of normalized column names to actual column names
    df_cols_map = {normalize_name(col): col for col in df.columns}
    
    partners = {}
    print("Processing rows...")
    if progress_callback: progress_callback(f"Processing {len(df)} rows...")

    errors = 0
    skipped_no_rejections = 0
    
    for index, row in df.iterrows():
        try:
            # Determine Partner Name
            partner_col = config['meta_map']['partner']
            partner_name = str(safe_get(row, partner_col, df_cols_map)).strip()
            
            if not partner_name or partner_name.lower() in ['nan', '']:
                continue
                
            if partner_name not in partners:
                partners[partner_name] = []

            rejected_images = []
            row_has_rejection_mark = False
            
            # Check for rejections based on config
            for status_col, status_val, stage_name, img_col, reason_col in config['checks']:
                actual_status = str(safe_get(row, status_col, df_cols_map)).strip().lower()
                expected_status = str(status_val).strip().lower()
                
                # Check status (Case Insensitive)
                if actual_status == expected_status:
                    row_has_rejection_mark = True
                    img_url = safe_get(row, img_col, df_cols_map)
                    reason = str(safe_get(row, reason_col, df_cols_map) or 'No Reason Provided')
                    
                    # Store rejection (even if image is empty, we'll handle it in PDF)
                    rejected_images.append({'stage': stage_name, 'image': img_url, 'reason': reason})

            if row_has_rejection_mark:
                # Extract Meta Data
                batch_meta = {}
                for key, col_name in config['meta_map'].items():
                    val = safe_get(row, col_name, df_cols_map)
                    batch_meta[key] = str(val).strip()
                
                partners[partner_name].append({'meta': batch_meta, 'images': rejected_images})
            else:
                skipped_no_rejections += 1
                
        except Exception as row_error:
            errors += 1
            print(f"Error processing row {index}: {row_error}")
            continue

    generated_files = []
    print(f"Found {len(partners)} partners with rejections. (Total Rows: {len(df)}, Errors: {errors}, No Rejections: {skipped_no_rejections})")
    if progress_callback: progress_callback(f"Found {len(partners)} partners. Generating PDFs...", percent=5)

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    total_partners = len(partners)
    completed_count = 0
    start_time = time.time()
    
    # Helper for parallel execution
    def process_one_partner(item):
        p_name, p_batches = item
        safe_name = "".join([c if c.isalnum() else "_" for c in p_name])
        f_name = os.path.join(OUTPUT_DIR, f"Report_{safe_name}.pdf")
        try:
            # Only pass progress callback if we have very few partners, otherwise it's too noisy/flickering
            # or pass a lambda that doesn't overwrite percent
            cb = progress_callback if len(partners) < 3 else None
            res_path = create_partner_pdf(p_name, p_batches, f_name, progress_callback=cb)
            return res_path
        except Exception as e:
            print(f"Error generating PDF for {p_name}: {e}")
            return None

    # Use ThreadPoolExecutor for parallel PDF generation
    # Adjust max_workers as needed (5-10 implies 5-10 concurrent PDF generations)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(process_one_partner, item): item for item in partners.items()}
        
        for future in concurrent.futures.as_completed(futures):
            completed_count += 1
            result = future.result()
            if result:
                generated_files.append(result)
            
            # Progress Logic
            percent = 5 + int((completed_count / total_partners) * 90) # 5% to 95%
            
            # ETA Logic
            elapsed = time.time() - start_time
            avg_time_per_item = elapsed / completed_count
            remaining = total_partners - completed_count
            eta_seconds = remaining * avg_time_per_item
            
            # Format ETA
            if eta_seconds < 60:
                eta_str = f"{int(eta_seconds)}s"
            else:
                eta_str = f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s"

            msg = f"Generated {completed_count}/{total_partners} reports"
            print(f"{msg}... ETA: {eta_str}")
            if progress_callback: 
                progress_callback(msg, percent=percent, eta=eta_str)

    if generated_files:
        return True, "Reports generated successfully.", generated_files
    else:
        if errors > 0:
            return True, f"Processed with {errors} row errors. No rejections found.", []
        return True, "No rejections found in the data. No reports generated.", []

if __name__ == "__main__":
    pass