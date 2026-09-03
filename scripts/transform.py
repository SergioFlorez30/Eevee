import csv
import re
from datetime import datetime
from io import BytesIO
from config.mapping import *

try:
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.worksheet.datavalidation import DataValidation
except ImportError:
    openpyxl = None

# ============================================================================
# DATE PARSING
# ============================================================================
def parse_date(value):
    """Parse date in multiple formats. Returns (day, month_name, year) or (None, None, None)."""
    if not value or str(value).strip() == "":
        return None, None, None
    
    value = str(value).strip()
    
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]:
        try:
            dt = datetime.strptime(value, fmt)
            month_name = MONTH_MAP.get(dt.month, "")
            return dt.day, month_name, dt.year
        except ValueError:
            continue
    
    return None, None, None

# ============================================================================
# CURRENCY CLEANING
# ============================================================================
def clean_currency(value):
    """Clean currency values. Handles both European (1.234,56) and American (1,234.56) formats."""
    if not value or str(value).strip() == "":
        return None
    
    value = str(value).strip().replace("$", "").strip()
    
    # Detect format by checking which separator appears last
    dot_index = value.rfind(".")
    comma_index = value.rfind(",")
    
    if dot_index > comma_index:
        # American format: 1,234.56
        value = value.replace(",", "")
    elif comma_index > dot_index:
        # European format: 1.234,56
        value = value.replace(".", "").replace(",", ".")
    
    try:
        return float(value)
    except ValueError:
        return None

# ============================================================================
# COUNTRY EXTRACTION
# ============================================================================
def extract_country_from_filename(filename):
    """Extract valid country code from filename."""
    for code in COUNTRY_CODES:
        if code in filename.upper():
            return code
    return ""

# ============================================================================
# GENDER & AGE EXTRACTION
# ============================================================================
def extract_gender(target_audience):
    """Extract gender from Target Audience prefix."""
    if not target_audience or str(target_audience).strip() == "":
        return ""
    
    parts = str(target_audience).split("_")
    if not parts:
        return ""
    
    prefix = parts[0].upper()
    for key, value in GENDER_MAP.items():
        if prefix.startswith(key):
            return value
    
    return ""

def extract_age_range(target_audience):
    """Extract age range from Target Audience suffix."""
    if not target_audience or str(target_audience).strip() == "":
        return ""
    
    parts = str(target_audience).split("_")
    if len(parts) > 1:
        return parts[1]
    
    return ""

# ============================================================================
# SUB SECTOR EXTRACTION
# ============================================================================
def extract_sub_sector(line_item):
    """Extract sub-sector from Line Item (text ending in 'Care')."""
    if not line_item or str(line_item).strip() == "":
        return ""
    
    match = re.search(r"(\w+\s+Care)", str(line_item))
    if match:
        return match.group(1)
    
    return ""

# ============================================================================
# STAGE NORMALIZATION
# ============================================================================
def normalize_stage(value):
    """Normalize stage from Media Objective."""
    if not value or str(value).strip() == "":
        return ""
    
    value_lower = str(value).lower().strip()
    return STAGE_MAPPING.get(value_lower, "")

# ============================================================================
# LINE ITEM PARSING
# ============================================================================
def _is_code_segment(segment):
    """Detect if segment is a code (taxonomy) vs. initiative text."""
    segment = segment.strip()
    
    # Check for code patterns: IO/LI/ADG + digits, or 3+ alphanum + "_"
    if re.match(r"^(IO|LI|ADG)\d+", segment):
        return True
    if re.match(r"^[A-Z0-9]{3,}_.+", segment):
        return True
    
    return False

def _split_line_item(line_item):
    """Split Line Item into initiative parts and code parts."""
    if not line_item or str(line_item).strip() == "":
        return [], []
    
    parts = [p.strip() for p in str(line_item).split("->")]
    initiative_parts = []
    code_parts = []
    found_code = False
    
    for part in parts:
        if not found_code and not _is_code_segment(part):
            initiative_parts.append(part)
        else:
            found_code = True
            code_parts.append(part)
    
    return initiative_parts, code_parts

def determine_level_dv360(line_item):
    """Determine LEVEL for DV360 from Line Item hierarchy."""
    initiative_parts, code_parts = _split_line_item(line_item)
    
    if not code_parts:
        return None, None
    
    last_code = code_parts[-1]
    
    if last_code.startswith("ADG"):
        return "Ad Group", last_code
    elif last_code.startswith("LI"):
        return "Line Item", last_code
    elif last_code.startswith("IO"):
        return "Insertion Order", last_code
    else:
        return "Campaign", last_code

def determine_level_plan_level(plan_level_value):
    """Determine LEVEL for plan-based platforms from Plan Level column."""
    if not plan_level_value or str(plan_level_value).strip() == "":
        return None
    
    value_str = str(plan_level_value).lower().strip()
    if value_str == "true":
        return "Campaign"
    elif value_str == "false":
        return "Ad Group"
    
    return None

def extract_taxo(line_item, platform):
    """Extract taxonomy code (CAMPAIGN_TAXO) from Line Item."""
    _, code_parts = _split_line_item(line_item)
    
    if not code_parts:
        return ""
    
    return code_parts[-1]

# ============================================================================
# ID GENERATION
# ============================================================================
def generate_ids(processed_rows):
    """Generate hierarchical IDs based on platform and code hierarchy."""
    ids = {}
    counter_map = {}  # (platform, parent_tuple) -> next_number
    
    for original_index, row in processed_rows:
        platform = row.get("PLATFORM", "")
        code_parts = row.get("_code_parts", [])
        
        if not code_parts:
            continue
        
        config = PLATFORM_CONFIG.get(platform, {})
        prefix = config.get("prefix", "X")
        
        # Convert code_parts to tuple for hashing
        parent_tuple = tuple(code_parts[:-1]) if len(code_parts) > 1 else ()
        key = (platform, parent_tuple)
        
        if key not in counter_map:
            counter_map[key] = 1
        
        current_num = counter_map[key]
        
        if parent_tuple:
            # Child segment: find parent ID and append
            parent_key = (platform, parent_tuple[:-1] if len(parent_tuple) > 1 else ())
            if parent_key in ids.values():
                parent_id = [v for k, v in ids.items() if k[1] == parent_key][0]
                id_str = f"{parent_id}-{current_num}"
            else:
                id_str = f"{prefix}{current_num}"
        else:
            # Root segment
            id_str = f"{prefix}{current_num}"
        
        ids[original_index] = id_str
        counter_map[key] += 1
    
    return ids

# ============================================================================
# MAIN TRANSFORMATION
# ============================================================================
def parse_csv(csv_text):
    """Parse CSV text into list of dicts."""
    reader = csv.DictReader(csv_text.strip().split('\n'))
    return list(reader)

def transform(cm_rows, filename):
    """Transform CM rows to ALFRED format. Returns (output_rows[], errors[])."""
    output_rows = []
    errors = []
    processed_rows = []
    
    # ========== PASS 1: Determine levels and collect processable rows ==========
    for idx, row in enumerate(cm_rows):
        platform = row.get("Platform", "").strip()
        line_item = row.get("Line Item", "").strip()
        plan_level = row.get("Plan Level", "").strip()
        
        if platform not in PLATFORM_CONFIG:
            continue
        
        config = PLATFORM_CONFIG[platform]
        
        if config.get("uses_plan_level"):
            level = determine_level_plan_level(plan_level)
        else:
            level, taxo = determine_level_dv360(line_item)
        
        if level is None:
            continue  # Skip filler rows
        
        # Extract code parts for ID generation
        _, code_parts = _split_line_item(line_item)
        
        row_data = {
            "PLATFORM": platform,
            "LEVEL": level,
            "_code_parts": code_parts,
            "_original_row": row,
            "_original_index": idx,
        }
        
        processed_rows.append((idx, row_data))
    
    # ========== PASS 2: Generate hierarchical IDs ==========
    id_map = generate_ids(processed_rows)
    
    # ========== PASS 3: Build output rows ==========
    for original_index, row_data in processed_rows:
        original_row = row_data["_original_row"]
        platform = row_data["PLATFORM"]
        level = row_data["LEVEL"]
        
        output_row = {}
        
        # Apply DIRECT_MAPPING
        for cm_field, alfred_field in DIRECT_MAPPING.items():
            output_row[alfred_field] = original_row.get(cm_field, "")
        
        # Apply FIXED_VALUES (all platforms)
        for field, value in FIXED_VALUES.items():
            output_row[field] = value
        
        # Apply PLATFORM_SPECIFIC_DEFAULTS (DV360 only for PACING initial value)
        if platform in PLATFORM_SPECIFIC_DEFAULTS:
            for field, value in PLATFORM_SPECIFIC_DEFAULTS[platform].items():
                output_row[field] = value
        
        # Parse dates
        start_day, start_month, start_year = parse_date(original_row.get("Start Date", ""))
        output_row["START_DAY"] = start_day or ""
        output_row["START_MONTH"] = start_month or ""
        output_row["START_YEAR"] = start_year or ""
        
        end_day, end_month, end_year = parse_date(original_row.get("End Date", ""))
        output_row["END_DAY"] = end_day or ""
        output_row["END_MONTH"] = end_month or ""
        output_row["END_YEAR"] = end_year or ""
        
        # Extract MONTH from Start Date
        if start_month:
            output_row["MONTH"] = start_month
        else:
            output_row["MONTH"] = ""
        
        # Clean currency
        output_row["BUDGET"] = clean_currency(original_row.get("Billable Budget", "")) or ""
        output_row["TOTAL_BUDGET"] = clean_currency(original_row.get("Total Budget", "")) or ""
        
        # Extract country from filename
        output_row["COUNTRY"] = extract_country_from_filename(filename)
        
        # Extract sub-sector
        output_row["SUB_SECTOR"] = extract_sub_sector(original_row.get("Line Item", ""))
        
        # Set LEVEL
        output_row["LEVEL"] = level
        
        # Extract CAMPAIGN_TAXO
        output_row["CAMPAIGN_TAXO"] = extract_taxo(original_row.get("Line Item", ""), platform)
        
        # Generate ID
        output_row["ID"] = id_map.get(original_index, "")
        
        # Parse Target Audience
        target_audience = original_row.get("Target Audience", "")
        output_row["GENDER"] = extract_gender(target_audience)
        output_row["AGE_RANGE"] = extract_age_range(target_audience)
        
        # Normalize STAGE
        output_row["STAGE"] = normalize_stage(original_row.get("Media Objective", ""))
        
        # Set PRICE_TYPE
        output_row["PRICE_TYPE"] = PRICE_TYPE
        
        # Set TYPE and other manual fields (conditional on platform)
        output_row["TYPE"] = ""  # User will fill in Excel
        for field in MANUAL_FIELDS_COMMON:
            if field not in output_row:
                output_row[field] = ""
        
        # Add BID_VALUE and KPI_VALUE only for DV360 (but NOT for Campaign level)
        if platform == "DV360" and level != "Campaign":
            for field in MANUAL_FIELDS_DV360_ONLY:
                if field not in output_row:
                    output_row[field] = ""
        
        # Add BID_VALUE only for TikTok (KPI_VALUE remains NULL)
        if platform == "TikTok":
            for field in MANUAL_FIELDS_BID_VALUE:
                if field not in output_row:
                    output_row[field] = ""
        
        # Add BUDGET_TYPE only for Meta, TikTok
        if platform in ["Meta", "TikTok"]:
            for field in MANUAL_FIELDS_BUDGET_TYPE:
                if field not in output_row:
                    output_row[field] = ""
        
        # Set empty fields
        for field in EMPTY_FIELDS:
            if field not in output_row:
                output_row[field] = ""
        
        output_rows.append(output_row)
    
    # ========== VALIDATION ==========
    for row in output_rows:
        platform = row.get("PLATFORM", "")
        level = row.get("LEVEL", "")
        
        # Fields that must always be present
        mandatory_fields = set(ALFRED_MANDATORY)
        
        # PACING is mandatory only for DV360 (but NOT for Campaign level)
        if platform == "DV360" and level != "Campaign":
            mandatory_fields.add("PACING")
        else:
            mandatory_fields.discard("PACING")
        
        # BUDGET_TYPE is mandatory only for Meta, TikTok
        if platform in ["Meta", "TikTok"]:
            mandatory_fields.add("BUDGET_TYPE")
        else:
            mandatory_fields.discard("BUDGET_TYPE")
        
        # BID_VALUE is mandatory for DV360 (not Campaign), TikTok
        if platform == "DV360" and level != "Campaign":
            mandatory_fields.add("BID_VALUE")
        elif platform == "TikTok":
            mandatory_fields.add("BID_VALUE")
        else:
            mandatory_fields.discard("BID_VALUE")
        
        # KPI_VALUE is mandatory only for DV360 (not Campaign)
        if platform == "DV360" and level != "Campaign":
            mandatory_fields.add("KPI_VALUE")
        else:
            mandatory_fields.discard("KPI_VALUE")
        
        for field in mandatory_fields:
            value = row.get(field, "")
            if not value or (isinstance(value, (int, float)) and value == 0):
                errors.append(f"Row {output_rows.index(row) + 1}: Missing mandatory field '{field}'")
    
    return output_rows, errors

# ============================================================================
# EXCEL OUTPUT
# ============================================================================
def write_excel(output_rows, errors):
    """Generate XLSX file with openpyxl. Returns bytes."""
    if not openpyxl:
        return None
    
    wb = Workbook()
    ws = wb.active
    ws.title = "ALFRED"
    
    # Header styling
    header_fill = PatternFill(start_color="00205B", end_color="00205B", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    
    # Write headers
    for col_idx, field in enumerate(ALFRED_COLUMN_ORDER, start=1):
        cell = ws.cell(row=1, column=col_idx, value=field)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
    
    # Freeze header row
    ws.freeze_panes = "A2"
    
    # Yellow fill for manual fields
    yellow_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    
    # Write data rows
    for row_idx, row_data in enumerate(output_rows, start=2):
        platform = row_data.get("PLATFORM", "")
        level = row_data.get("LEVEL", "")
        
        # Determine which fields should be highlighted for this row's platform
        manual_fields_for_row = set(MANUAL_FIELDS_COMMON)
        
        # DV360: BID_VALUE and KPI_VALUE (but NOT for Campaign level)
        if platform == "DV360" and level != "Campaign":
            manual_fields_for_row.update(MANUAL_FIELDS_DV360_ONLY)
        
        # TikTok: Only BID_VALUE (not KPI_VALUE)
        if platform == "TikTok":
            manual_fields_for_row.update(MANUAL_FIELDS_BID_VALUE)
        
        # PACING is manual only for DV360 (but NOT for Campaign level)
        if platform == "DV360" and level != "Campaign":
            manual_fields_for_row.add("PACING")
        
        # BUDGET_TYPE is manual only for Meta, TikTok
        if platform in ["Meta", "TikTok"]:
            manual_fields_for_row.update(MANUAL_FIELDS_BUDGET_TYPE)
        
        for col_idx, field in enumerate(ALFRED_COLUMN_ORDER, start=1):
            value = row_data.get(field, "")
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            
            # Highlight manual fields (conditional on platform)
            if field in manual_fields_for_row:
                cell.fill = yellow_fill
            
            cell.alignment = Alignment(horizontal="left", vertical="center")
    
    # Add data validation for manual fields (dropdowns)
    if output_rows:
        status_validation = DataValidation(
            type="list",
            formula1=f'"{",".join(STATUS_OPTIONS)}"',
            allow_blank=False
        )
        
        pacing_validation = DataValidation(
            type="list",
            formula1=f'"{",".join(PACING_OPTIONS.get("DV360", []))}"',
            allow_blank=False
        )
        
        budget_type_validation = DataValidation(
            type="list",
            formula1=f'"{",".join(BUDGET_TYPE_OPTIONS.get("Meta", []))}"',
            allow_blank=False
        )
        
        imp_status_validation = DataValidation(
            type="list",
            formula1=f'"{",".join(IMP_STATUS_OPTIONS)}"',
            allow_blank=True
        )
        
        for col_idx, field in enumerate(ALFRED_COLUMN_ORDER, start=1):
            if field == "STATUS":
                for row_idx in range(2, len(output_rows) + 2):
                    status_validation.add(ws.cell(row=row_idx, column=col_idx))
            elif field == "PACING":
                # Add PACING validation only for DV360 rows (but NOT for Campaign level)
                for row_idx, row_data in enumerate(output_rows, start=2):
                    if row_data.get("PLATFORM") == "DV360" and row_data.get("LEVEL") != "Campaign":
                        pacing_validation.add(ws.cell(row=row_idx, column=col_idx))
            elif field == "BUDGET_TYPE":
                # Add BUDGET_TYPE validation only for Meta, TikTok rows
                for row_idx, row_data in enumerate(output_rows, start=2):
                    if row_data.get("PLATFORM") in ["Meta", "TikTok"]:
                        budget_type_validation.add(ws.cell(row=row_idx, column=col_idx))
            elif field == "IMP_STATUS":
                # Add IMP_STATUS validation for all rows
                for row_idx in range(2, len(output_rows) + 2):
                    imp_status_validation.add(ws.cell(row=row_idx, column=col_idx))
        
        ws.add_data_validation(status_validation)
        ws.add_data_validation(pacing_validation)
        ws.add_data_validation(budget_type_validation)
        ws.add_data_validation(imp_status_validation)
    
    # Error sheet (if errors exist)
    if errors:
        error_ws = wb.create_sheet("Errores")
        error_ws.append(["Error"])
        for error in errors:
            error_ws.append([error])
    
    # Set column widths
    for col_idx in range(1, len(ALFRED_COLUMN_ORDER) + 1):
        ws.column_dimensions[chr(64 + col_idx)].width = 15
    
    # Save to bytes
    output = BytesIO()
    wb.save(output)
    return output.getvalue()

# ============================================================================
# ENTRY POINT (Called from Pyodide via app.js)
# ============================================================================
def run(csv_text, filename):
    """Main transformation entry point. Returns dict with results."""
    try:
        cm_rows = parse_csv(csv_text)
        output_rows, errors = transform(cm_rows, filename)
        
        excel_bytes = write_excel(output_rows, errors)
        
        return {
            "excel_bytes": excel_bytes,
            "errors": errors,
            "row_count": len(output_rows),
            "has_errors": len(errors) > 0,
        }
    except Exception as e:
        return {
            "excel_bytes": None,
            "errors": [f"Fatal error: {str(e)}"],
            "row_count": 0,
            "has_errors": True,
        }
