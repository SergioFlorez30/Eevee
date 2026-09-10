import csv
import re
from datetime import datetime
from io import BytesIO
from config.mapping import *

try:
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.utils import get_column_letter
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

# ============================================================================
# DATE PARSING
# ============================================================================
def parse_date(value):
    """Parse date in multiple formats. Returns (day, month_number, year) or (None, None, None)."""
    if not value or str(value).strip() == "":
        return None, None, None
    
    value = str(value).strip()
    
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.day, dt.month, dt.year
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
    # Per CM export behavior agreed with stakeholders:
    # false -> Campaign, true -> Ad Group
    if value_str == "false":
        return "Campaign"
    elif value_str == "true":
        return "Ad Group"
    elif value_str == "campaign":
        return "Campaign"
    elif value_str in ["ad group", "adgroup"]:
        return "Ad Group"
    
    return None

def determine_level_two_tier(line_item):
    """Determine level for non-DV360 platforms using parent-child hierarchy only.

    These platforms are modeled with two levels:
    - Campaign
    - Ad Group
    """
    _, code_parts = _split_line_item(line_item)
    if not code_parts:
        return None

    last_code = str(code_parts[-1]).strip().upper()
    if last_code.startswith("ADG"):
        return "Ad Group"
    return "Campaign"

def normalize_platform(platform_value, publisher_value=""):
    """Normalize CM platform values to Alfred catalog values."""
    platform_raw = str(platform_value or "").strip()
    publisher_raw = str(publisher_value or "").strip()

    if platform_raw in PLATFORM_CONFIG:
        return platform_raw

    platform_alias = PLATFORM_ALIASES.get(platform_raw.lower(), "")
    if platform_alias:
        return platform_alias

    if publisher_raw in PLATFORM_CONFIG:
        return publisher_raw

    publisher_alias = PLATFORM_ALIASES.get(publisher_raw.lower(), "")
    if publisher_alias:
        return publisher_alias

    return platform_raw

def build_lineage_keys(line_item):
    """Build cumulative lineage keys from line item hierarchy for parent-child inheritance."""
    if not line_item or str(line_item).strip() == "":
        return []

    parts = [p.strip() for p in str(line_item).split("->") if p.strip()]
    keys = []
    for i in range(1, len(parts) + 1):
        keys.append(" -> ".join(parts[:i]))
    return keys

def extract_taxo(line_item, platform):
    """Extract taxonomy code (CAMPAIGN_TAXO) from Line Item."""
    _, code_parts = _split_line_item(line_item)
    
    if not code_parts:
        return ""
    
    return code_parts[-1]

def infer_type(platform, level, effective_row):
    """Infer TYPE from configured options and source row context."""
    options = TYPE_OPTIONS.get((platform, level), [])
    if not options:
        return ""

    if len(options) == 1:
        return options[0]

    # Use key source fields as matching context for multi-option cases.
    context_values = [
        effective_row.get("Platform", ""),
        effective_row.get("Publisher", ""),
        effective_row.get("Line Item", ""),
        effective_row.get("Media SubType", ""),
        effective_row.get("OU Media Sub-Type", ""),
        effective_row.get("OU Media SubType", ""),
        effective_row.get("Site", ""),
    ]
    context = " | ".join(str(v) for v in context_values if v).lower()
    context_token = _norm_token(context)

    # Match explicit options first.
    for option in options:
        if option.lower() in context:
            return option
        if _norm_token(option) and _norm_token(option) in context_token:
            return option

    # Normalize frequent naming variants for all platforms.
    aliases = {
        "nonskip": "Non-Skip",
        "nonskipvideo": "Non-Skip",
        "skip": "Skip",
        "bumper": "Bumper",
        "oxdisplay": "OX Display",
        "oxvideo": "OX Video",
        "ytshorts": "YT Shorts",
        "youtube": "Youtube",
        "programmatic": "Programmatic",
        "pmpguaranteed": "PMP Guaranteed",
        "pmpnonguaranteed": "PMP Non Guaranteed",
        "lineups": "Lineups",
        "masthead": "Masthead",
        "pauseads": "Pause Ads",
        "topview": "Top View",
        "topfeed": "Top Feed",
        "tiktoksearch": "TikTok Search",
        "tiktokshop": "TikTok Shop",
        "googlesearch": "Google Search",
        "googleads": "Google Ads",
        "amazonprime": "Amazon Prime",
        "facebookinstagram": "Meta",
    }
    for key, mapped in aliases.items():
        if key in context_token and mapped in options:
            return mapped

    # Deterministic fallback for matrix options that include NA.
    if "NA" in options:
        return "NA"

    # No reliable inference found.
    return ""

def _is_empty_or_na(value):
    text = str(value or "").strip()
    return text == "" or text.upper() in ["N/A", "NA", "NULL", "NONE"]

def resolve_pricing_model(source_row):
    """Resolve PRICING_MODEL from CM using only Cost Type."""
    cost_type = source_row.get("Cost Type", "")

    if not _is_empty_or_na(cost_type):
        return str(cost_type).strip()
    return ""

def _norm_token(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())

def normalize_bid_type_key(value):
    """Map raw condition values to canonical BID_TYPE_OPTIONS keys."""
    token = _norm_token(value)
    aliases = {
        "videoviews": "Video Views",
        "sitetraffic": "Site Traffic",
        "reach": "Reach",
        "youtube": "Youtube",
        "nonskip": "Non_Skip",
        "skip": "Skip",
        "pmpnonguaranteed": "PMP_Non_Guaranteed",
        "bumper": "Bumper",
    }
    return aliases.get(token, "")

def get_bid_type_options_for_row(row_data):
    """Return BID_TYPE_OPTIMIZATION_TYPE options for the row conditions."""
    platform = row_data.get("PLATFORM", "")
    if not platform:
        return []

    # Strict condition mapping from the agreed matrix:
    # - DV360 keys come from TYPE-like values
    # - Meta/TikTok keys come from CAMPAIGN_GOAL
    candidate_values = []
    if platform == "DV360":
        candidate_values = [
            row_data.get("TYPE", ""),
            row_data.get("Media SubType", ""),
            row_data.get("OU Media Sub-Type", ""),
            row_data.get("OU Media SubType", ""),
            row_data.get("Site", ""),
        ]
    elif platform in ["Meta", "TikTok"]:
        candidate_values = [
            row_data.get("CAMPAIGN_GOAL", ""),
            row_data.get("TYPE", ""),
        ]

    for value in candidate_values:
        canonical = normalize_bid_type_key(value)
        if not canonical:
            continue
        options = BID_TYPE_OPTIONS.get((platform, canonical), [])
        if options:
            return options

    # No condition match -> no dropdown for this row.
    return []

# ============================================================================
# ID GENERATION
# ============================================================================
def generate_ids(processed_rows):
    """Generate hierarchical IDs based on platform and code hierarchy."""
    ids = {}
    counter_map = {}  # (platform, parent_tuple) -> next_number
    id_by_path = {}   # (platform, code_path_tuple) -> generated ID
    
    for original_index, row in processed_rows:
        platform = row.get("PLATFORM", "")
        code_parts = row.get("_code_parts", [])
        
        if not code_parts:
            continue
        
        config = PLATFORM_CONFIG.get(platform, {})
        prefix = config.get("prefix", "X")
        
        code_path = tuple(code_parts)
        parent_tuple = code_path[:-1]
        counter_key = (platform, parent_tuple)

        if counter_key not in counter_map:
            counter_map[counter_key] = 1

        current_num = counter_map[counter_key]

        if parent_tuple:
            parent_id = id_by_path.get((platform, parent_tuple), "")
            if parent_id:
                id_str = f"{parent_id}-{current_num}"
            else:
                id_str = f"{prefix}{current_num}"
        else:
            id_str = f"{prefix}{current_num}"

        ids[original_index] = id_str
        id_by_path[(platform, code_path)] = id_str
        counter_map[counter_key] += 1
    
    return ids

def reconcile_parent_budgets(output_rows):
    """If immediate children have budget and parent campaign has 0/empty, set parent as children sum."""
    for row in output_rows:
        code_parts = row.get("__CODE_PARTS", [])
        if isinstance(code_parts, list):
            row["__CODE_PARTS"] = tuple(code_parts)

    for parent_row in output_rows:
        platform = parent_row.get("PLATFORM", "")
        level = parent_row.get("LEVEL", "")
        parent_code = parent_row.get("__CODE_PARTS", ())

        if level != "Campaign" or not parent_code:
            continue

        immediate_children = [
            child for child in output_rows
            if child.get("PLATFORM", "") == platform
            and len(child.get("__CODE_PARTS", ())) == len(parent_code) + 1
            and child.get("__CODE_PARTS", ())[:len(parent_code)] == parent_code
        ]

        if not immediate_children:
            continue

        for field in ["BUDGET", "TOTAL_BUDGET"]:
            child_values = []
            for child in immediate_children:
                value = child.get(field, "")
                if value is None or str(value).strip() == "":
                    continue
                try:
                    child_values.append(float(value))
                except (ValueError, TypeError):
                    continue

            if not child_values:
                continue

            parent_value = parent_row.get(field, "")
            try:
                parent_num = float(parent_value)
            except (ValueError, TypeError):
                parent_num = None

            if parent_num is None or parent_num == 0:
                parent_row[field] = sum(child_values)

# ============================================================================
# MAIN TRANSFORMATION
# ============================================================================
def parse_csv(csv_text):
    """Parse CM CSV text into list of dicts.

    Handles common CM export quirks:
    - A decorative first row above the real header.
    - Header casing differences (for example, "Plan level").
    - Repeated header names (for example, "Publisher", "Target Audience").
    """
    if not csv_text or str(csv_text).strip() == "":
        return []

    header_aliases = {
        "Plan level": "Plan Level",
    }

    expected_headers = {
        "Platform",
        "Line Item",
        "Plan Level",
        "Plan level",
        "Start Date",
        "End Date",
        "Brand",
        "Sub Brand",
        "Total Budget",
        "Billable Budget",
        "Target Audience",
        "Media Objective",
        "Initiative",
        "Cost Type",
        "Publisher",
    }

    rows = list(csv.reader(csv_text.splitlines()))
    # Keep rows that have at least one non-empty value.
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    if not rows:
        return []

    # Detect the most likely header row by overlap with expected CM columns.
    header_row_index = 0
    best_score = -1
    for idx, row in enumerate(rows):
        score = sum(1 for cell in row if str(cell).strip() in expected_headers)
        if score > best_score:
            best_score = score
            header_row_index = idx

    raw_header = rows[header_row_index]
    header = []
    for cell in raw_header:
        key = str(cell).strip()
        key = header_aliases.get(key, key)
        header.append(key)

    parsed_rows = []
    for raw_row in rows[header_row_index + 1:]:
        # Align row length with header length.
        if len(raw_row) < len(header):
            raw_row = raw_row + [""] * (len(header) - len(raw_row))

        row_dict = {}
        for col_idx, key in enumerate(header):
            if not key:
                continue

            value = str(raw_row[col_idx]).strip() if col_idx < len(raw_row) else ""

            # For duplicate headers, keep the first non-empty value.
            if key not in row_dict or row_dict[key] == "":
                row_dict[key] = value

        parsed_rows.append(row_dict)

    return parsed_rows

def transform(cm_rows, filename):
    """Transform CM rows to ALFRED format. Returns (output_rows[], errors[])."""
    output_rows = []
    errors = []
    processed_rows = []
    inheritance_cache = {}
    inheritable_fields = set(DIRECT_MAPPING.keys()) | {
        "Platform",
        "Publisher",
        "Plan Level",
        "Start Date",
        "End Date",
        "Billable Budget",
        "Total Budget",
        "Target Audience",
        "Media Objective",
        "Line Item",
    }
    
    # ========== PASS 1: Determine levels and collect processable rows ==========
    for idx, row in enumerate(cm_rows):
        normalized_row = {
            key: (str(value).strip() if value is not None else "")
            for key, value in row.items()
        }

        line_item = normalized_row.get("Line Item", "")
        lineage_keys = build_lineage_keys(line_item)

        # Inherit missing values from ancestor rows in the same lineage.
        effective_row = dict(normalized_row)
        inherited_values = {}
        for lineage_key in lineage_keys:
            cached = inheritance_cache.get(lineage_key, {})
            for field, value in cached.items():
                if value:
                    inherited_values[field] = value

        for field in inheritable_fields:
            if not effective_row.get(field, ""):
                inherited_value = inherited_values.get(field, "")
                if inherited_value:
                    effective_row[field] = inherited_value

        platform = normalize_platform(
            effective_row.get("Platform", ""),
            effective_row.get("Publisher", ""),
        )
        effective_row["Platform"] = platform

        # Update inheritance cache for this lineage key so children can reuse parent values.
        if lineage_keys:
            current_key = lineage_keys[-1]
            current_cache = dict(inheritance_cache.get(current_key, {}))
            for field in inheritable_fields:
                field_value = effective_row.get(field, "")
                if field_value:
                    current_cache[field] = field_value
            inheritance_cache[current_key] = current_cache

        if platform not in PLATFORM_CONFIG:
            continue
        
        config = PLATFORM_CONFIG[platform]
        
        if config.get("uses_plan_level"):
            # Do not rely on Plan Level for non-DV360 due CM inconsistency.
            level = determine_level_two_tier(line_item)
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
            "_effective_row": effective_row,
            "_original_index": idx,
        }
        
        processed_rows.append((idx, row_data))
    
    # ========== PASS 2: Generate hierarchical IDs ==========
    id_map = generate_ids(processed_rows)
    
    # ========== PASS 3: Build output rows ==========
    for original_index, row_data in processed_rows:
        original_row = row_data["_effective_row"]
        platform = row_data["PLATFORM"]
        level = row_data["LEVEL"]
        
        output_row = {}
        
        # Apply DIRECT_MAPPING
        for cm_field, alfred_field in DIRECT_MAPPING.items():
            output_row[alfred_field] = original_row.get(cm_field, "")

        # Resolve PRICING_MODEL robustly when CM sends Cost Type as N/A.
        output_row["PRICING_MODEL"] = resolve_pricing_model(original_row)
        
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
        
        # MONTH keeps Alfred month code (SEP, OCT, ...), while START/END_MONTH stay numeric.
        if start_month:
            output_row["MONTH"] = MONTH_MAP.get(start_month, "")
        else:
            output_row["MONTH"] = ""
        
        # Clean currency
        budget_value = clean_currency(original_row.get("Billable Budget", ""))
        total_budget_value = clean_currency(original_row.get("Total Budget", ""))
        output_row["BUDGET"] = "" if budget_value is None else budget_value
        output_row["TOTAL_BUDGET"] = "" if total_budget_value is None else total_budget_value
        
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
        output_row["__CODE_PARTS"] = tuple(row_data.get("_code_parts", []))
        
        # Parse Target Audience
        target_audience = original_row.get("Target Audience", "")
        output_row["GENDER"] = extract_gender(target_audience)
        output_row["AGE_RANGE"] = extract_age_range(target_audience)
        
        # Normalize STAGE
        output_row["STAGE"] = normalize_stage(original_row.get("Media Objective", ""))
        
        # Set PRICE_TYPE
        output_row["PRICE_TYPE"] = PRICE_TYPE
        
        # Set TYPE using configured business rules.
        output_row["TYPE"] = infer_type(platform, level, original_row)

        # Set other manual fields (conditional on platform)
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

    # Parent campaigns can inherit budget totals from immediate children when parent is 0/empty.
    reconcile_parent_budgets(output_rows)
    
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

        # BUDGET_TYPE is mandatory only for Meta and TikTok.
        if platform in ["Meta", "TikTok"]:
            mandatory_fields.add("BUDGET_TYPE")
        else:
            mandatory_fields.discard("BUDGET_TYPE")

        # Manual fields are expected to be filled by users in the generated Excel,
        # so they should not block output generation.
        manual_fields_for_row = set(MANUAL_FIELDS_COMMON)
        if platform == "DV360" and level != "Campaign":
            manual_fields_for_row.update(MANUAL_FIELDS_DV360_ONLY)
            manual_fields_for_row.add("PACING")
        if platform == "TikTok":
            manual_fields_for_row.update(MANUAL_FIELDS_BID_VALUE)
        if platform in ["Meta", "TikTok"]:
            manual_fields_for_row.update(MANUAL_FIELDS_BUDGET_TYPE)

        mandatory_fields = mandatory_fields - manual_fields_for_row
        
        for field in mandatory_fields:
            value = row.get(field, "")
            if value is None or str(value).strip() == "":
                errors.append(f"Row {output_rows.index(row) + 1}: Missing mandatory field '{field}'")
    
    return output_rows, errors

# ============================================================================
# EXCEL OUTPUT
# ============================================================================
def write_excel(output_rows, errors):
    """Generate XLSX file with openpyxl. Returns bytes."""
    if not OPENPYXL_AVAILABLE:
        return None
    wb = Workbook()
    ws = wb.active
    ws.title = "ALFRED"

    # Header styling by section
    header_fill_default = PatternFill(start_color="000000", end_color="000000", fill_type="solid")
    header_fill_purple = PatternFill(start_color="7A287D", end_color="7A287D", fill_type="solid")
    header_fill_blue = PatternFill(start_color="0D2D6C", end_color="0D2D6C", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )

    # Row color rules for Campaign level by platform (apply through PLATFORM_ID).
    campaign_platform_fill = {
        "DV360": PatternFill(start_color="BAF7B7", end_color="BAF7B7", fill_type="solid"),
        "Meta": PatternFill(start_color="B4C6E7", end_color="B4C6E7", fill_type="solid"),
        "TikTok": PatternFill(start_color="EA9999", end_color="EA9999", fill_type="solid"),
        "Pinterest": PatternFill(start_color="F7FCB2", end_color="F7FCB2", fill_type="solid"),
        "Google Ads": PatternFill(start_color="F9CB9C", end_color="F9CB9C", fill_type="solid"),
        "Amazon Prime": PatternFill(start_color="FFC2EB", end_color="FFC2EB", fill_type="solid"),
    }

    # STATUS color rules
    status_fill_map = {
        "OFF": PatternFill(start_color="8B0000", end_color="8B0000", fill_type="solid"),
        "ON": PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid"),
    }
    status_font_map = {
        "OFF": Font(name="Calibri", size=11, color="FFFFFF"),
        "ON": Font(name="Calibri", size=11, color="000000"),
    }
    manual_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")

    base_font = Font(name="Calibri", size=11)
    bold_font = Font(name="Calibri", size=11, bold=True)
    platform_id_col_idx = ALFRED_COLUMN_ORDER.index("PLATFORM_ID") + 1
    status_col_idx = ALFRED_COLUMN_ORDER.index("STATUS") + 1

    purple_header_fields = {
        "BUDGET_TYPE",
        "PACING",
        "BID_TYPE_OPTIMIZATION_TYPE",
        "BID_VALUE",
        "KPI_VALUE",
        "PLATFORM_ID",
        "STATUS",
    }
    blue_header_fields = {
        "IMP_STATUS",
        "IMP_STATUS_DATE",
        "QA_STATUS",
        "QA_DATE",
        "LIVE_CHECK",
        "LIVE_CHECK_DATE",
        "LIVE_CHECK_STATUS",
        "INITIAL_CAMPAIGN_LAUNCH_DATE",
        "NOTES_QA",
        "NOTES_OPS",
    }

    # Write headers
    for col_idx, field in enumerate(ALFRED_COLUMN_ORDER, start=1):
        cell = ws.cell(row=1, column=col_idx, value=field)
        if field in purple_header_fields:
            cell.fill = header_fill_purple
        elif field in blue_header_fields:
            cell.fill = header_fill_blue
        else:
            cell.fill = header_fill_default
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    # Freeze header row
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 22
    
    # Write data rows
    for row_idx, row_data in enumerate(output_rows, start=2):
        platform = row_data.get("PLATFORM", "")
        level = row_data.get("LEVEL", "")

        # Manual fields are always yellow, with priority over row-level colors.
        manual_fields_for_row = set(MANUAL_FIELDS_COMMON)
        if platform == "DV360" and level != "Campaign":
            manual_fields_for_row.update(MANUAL_FIELDS_DV360_ONLY)
            manual_fields_for_row.add("PACING")
        if platform == "TikTok":
            manual_fields_for_row.update(MANUAL_FIELDS_BID_VALUE)
        if platform in ["Meta", "TikTok"]:
            manual_fields_for_row.update(MANUAL_FIELDS_BUDGET_TYPE)

        # Determine row-level color logic.
        is_bold_row = level in ["Campaign", "Insertion Order"]
        is_campaign = level == "Campaign"
        campaign_fill = campaign_platform_fill.get(platform)
        status_value = str(row_data.get("STATUS", "")).strip().upper()
        
        for col_idx, field in enumerate(ALFRED_COLUMN_ORDER, start=1):
            value = row_data.get(field, "")
            cell = ws.cell(row=row_idx, column=col_idx, value=value)

            if is_bold_row:
                cell.font = bold_font
            else:
                cell.font = base_font

            cell.border = thin_border

            # Default data area background is white.
            cell.fill = white_fill

            # Campaign row color applies from first column through PLATFORM_ID only.
            if is_campaign and campaign_fill and col_idx <= platform_id_col_idx:
                cell.fill = campaign_fill

            # Manual fields take precedence over platform row coloring.
            if field in manual_fields_for_row:
                cell.fill = manual_fill

            # STATUS color override applies to STATUS column regardless of row color.
            if col_idx == status_col_idx and status_value in status_fill_map:
                cell.fill = status_fill_map[status_value]
                cell.font = status_font_map[status_value]

            cell.alignment = Alignment(horizontal="left", vertical="center")

        ws.row_dimensions[row_idx].height = 20
    
    # Add data validation for manual fields (dropdowns)
    if output_rows:
        list_ws = wb.create_sheet("_lists")
        list_ws.sheet_state = "hidden"

        list_cache = {}
        next_list_col = 1

        def list_range_formula(options):
            nonlocal next_list_col
            key = tuple(options)
            if key in list_cache:
                return list_cache[key]

            col_letter = get_column_letter(next_list_col)
            for row_idx, option in enumerate(options, start=1):
                list_ws.cell(row=row_idx, column=next_list_col, value=option)

            formula = f"'{list_ws.title}'!${col_letter}$1:${col_letter}${len(options)}"
            list_cache[key] = formula
            next_list_col += 1
            return formula

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

        type_validations = []
        bid_type_validations = []
        
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
            elif field == "TYPE":
                for row_idx, row_data in enumerate(output_rows, start=2):
                    platform = row_data.get("PLATFORM", "")
                    level = row_data.get("LEVEL", "")
                    type_options = TYPE_OPTIONS.get((platform, level), [])
                    if not type_options:
                        continue
                    formula = list_range_formula(type_options)
                    type_validation = DataValidation(
                        type="list",
                        formula1=f"={formula}",
                        allow_blank=False,
                    )
                    type_validation.add(ws.cell(row=row_idx, column=col_idx))
                    type_validations.append(type_validation)
            elif field == "BID_TYPE_OPTIMIZATION_TYPE":
                for row_idx, row_data in enumerate(output_rows, start=2):
                    options = get_bid_type_options_for_row(row_data)
                    if not options:
                        continue
                    formula = list_range_formula(options)
                    bid_validation = DataValidation(
                        type="list",
                        formula1=f"={formula}",
                        allow_blank=True,
                    )
                    bid_validation.add(ws.cell(row=row_idx, column=col_idx))
                    bid_type_validations.append(bid_validation)
        
        ws.add_data_validation(status_validation)
        ws.add_data_validation(pacing_validation)
        ws.add_data_validation(budget_type_validation)
        ws.add_data_validation(imp_status_validation)
        for type_validation in type_validations:
            ws.add_data_validation(type_validation)
        for bid_validation in bid_type_validations:
            ws.add_data_validation(bid_validation)
    
    # Error sheet (if errors exist)
    if errors:
        error_ws = wb.create_sheet("Errores")
        error_ws.append(["Error"])
        for error in errors:
            error_ws.append([error])
    
    # Set column widths
    for col_idx in range(1, len(ALFRED_COLUMN_ORDER) + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 15
    
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
