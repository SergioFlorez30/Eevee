# config/mapping.py - Eevee Field Mapping Configuration
# Single source of truth for all CM → ALFRED transformation rules

# ============================================================================
# DIRECT MAPPING: Fields that copy directly from CM to ALFRED
# ============================================================================
DIRECT_MAPPING = {
    "Brand": "BRAND",
    "Sub Brand": "SUB_BRAND",
    "Platform": "PLATFORM",
    "Initiative": "INITIATIVE",
    "Autobidder Activation Flag": "AUTOBIDDERS",
    "Coupon (Actuals)": "BONO",
    "Cost Type": "PRICING_MODEL",
}

# ============================================================================
# FIXED VALUES: Fields that always output the same constant (all platforms)
# ============================================================================
FIXED_VALUES = {
    "BUY_TYPE": "Auction",
    "IRA_VERSION": "V1",
    "REGION": "National",
    "AUDIENCE": "Demo",
    "BROADCAST": "NA",
}

# ============================================================================
# PLATFORM-SPECIFIC DEFAULTS: Initial values, user can edit in Excel via dropdown
# ============================================================================
PLATFORM_SPECIFIC_DEFAULTS = {
    "DV360": {
        "PACING": "Daily_Even",  # Default, user can change via PACING_OPTIONS dropdown
    },
}

# ============================================================================
# PACING OPTIONS: Valid values for PACING field (DV360 only)
# ============================================================================
PACING_OPTIONS = {
    "DV360": [
        "Flight_Ahead",
        "Flight_Even",
        "Daily_Asap",
        "Daily_Even",
    ],
}

# ============================================================================
# BUDGET_TYPE OPTIONS: Valid values for BUDGET_TYPE field (Meta, TikTok only)
# ============================================================================
BUDGET_TYPE_OPTIONS = {
    "Meta": [
        "Standard",
        "Advantage",
    ],
    "TikTok": [
        "Standard",
        "Advantage",
    ],
}

# ============================================================================
# IMP_STATUS OPTIONS: Valid values for IMP_STATUS field (all platforms)
# ============================================================================
IMP_STATUS_OPTIONS = [
    "Implemented",
    "Pending",
    "Manual Imp.",
]

# ============================================================================
# MANUAL FIELDS: User must select/enter these in Excel after download
# ============================================================================
# Fields common to all platforms
MANUAL_FIELDS_COMMON = [
    "CAMPAIGN_GOAL",
    "PO",
    "FREQUENCY",
    "STATUS",
    "IMP_STATUS",
    "BID_TYPE_OPTIMIZATION_TYPE",
]

# Fields only for DV360
MANUAL_FIELDS_DV360_ONLY = [
    "BID_VALUE",
    "KPI_VALUE",
]

# Fields only for DV360 and TikTok
MANUAL_FIELDS_BID_VALUE = [
    "BID_VALUE",
]

# Fields only for Meta, TikTok
MANUAL_FIELDS_BUDGET_TYPE = [
    "BUDGET_TYPE",
]

# All manual fields (for backwards compatibility)
MANUAL_FIELDS = MANUAL_FIELDS_COMMON + MANUAL_FIELDS_DV360_ONLY + MANUAL_FIELDS_BID_VALUE + MANUAL_FIELDS_BUDGET_TYPE

# ============================================================================
# EMPTY FIELDS: Alfred accepts these as empty
# ============================================================================
EMPTY_FIELDS = [
    "DEAL_ID",
    "CITY",
    "TARGET_UU",
    "TARGET_IMPRESSIONS",
    "BRANDLIFT",
    "UPDATED",
    "UPDATE_DATE",
    "NOTES_PLANNING",
    "TEST",
    "TEST_VARIABLE",
    "KEY_METRIC",
    "IMP_STATUS_DATE",
    "QA_STATUS",
    "QA_DATE",
    "LIVE_CHECK",
    "LIVE_CHECK_DATE",
    "LIVE_CHECK_STATUS",
    "INITIAL_CAMPAIGN_LAUNCH_DATE",
    "NOTES_QA",
    "NOTES_OPS",
    "PLATFORM_ID",
]

# ============================================================================
# COLUMN ORDER: Exact sequence for ALFRED output (61 columns)
# ============================================================================
ALFRED_COLUMN_ORDER = [
    "COUNTRY",
    "SUB_SECTOR",
    "BRAND",
    "SUB_BRAND",
    "MONTH",
    "IRA_VERSION",
    "INITIATIVE",
    "PLATFORM",
    "ID",
    "LEVEL",
    "TYPE",
    "STAGE",
    "BUY_TYPE",
    "BROADCAST",
    "CAMPAIGN_GOAL",
    "PRICING_MODEL",
    "START_DAY",
    "START_MONTH",
    "START_YEAR",
    "END_DAY",
    "END_MONTH",
    "END_YEAR",
    "PO",
    "BUDGET",
    "BONO",
    "TOTAL_BUDGET",
    "DEAL_ID",
    "REGION",
    "CITY",
    "AUDIENCE",
    "GENDER",
    "AGE_RANGE",
    "CAMPAIGN_TAXO",
    "TARGET_UU",
    "FREQUENCY",
    "TARGET_IMPRESSIONS",
    "AUTOBIDDERS",
    "BRANDLIFT",
    "UPDATED",
    "UPDATE_DATE",
    "NOTES_PLANNING",
    "TEST",
    "TEST_VARIABLE",
    "KEY_METRIC",
    "BUDGET_TYPE",
    "PACING",
    "BID_TYPE_OPTIMIZATION_TYPE",
    "BID_VALUE",
    "KPI_VALUE",
    "PLATFORM_ID",
    "STATUS",
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
]

# ============================================================================
# MANDATORY FIELDS: If any of these are empty, block download with error
# ============================================================================
ALFRED_MANDATORY = [
    "COUNTRY",
    "SUB_SECTOR",
    "BRAND",
    "SUB_BRAND",
    "INITIATIVE",
    "CAMPAIGN_TAXO",
    "LEVEL",
    "ID",
    "PLATFORM",
    "TYPE",
    "START_DAY",
    "START_MONTH",
    "START_YEAR",
    "END_DAY",
    "END_MONTH",
    "END_YEAR",
    "TOTAL_BUDGET",
    "BUDGET",
    "BUDGET_TYPE",
    "GENDER",
    "AGE_RANGE",
    "MONTH",
    "STAGE",
    "PRICE_TYPE",
    "PRICING_MODEL",
    "BUY_TYPE",
    "REGION",
    "AUDIENCE",
]

# ============================================================================
# STAGE MAPPING: Normalize Media Objective to valid STAGE values
# ============================================================================
STAGE_MAPPING = {
    "performance": "Awareness",
    "data gathering": "Awareness",
    "awareness": "Awareness",
    "consideration": "Consideration",
    "conversion": "Conversion",
}

# ============================================================================
# GENDER MAPPING: Extract from Target Audience prefix
# ============================================================================
GENDER_MAP = {
    "W": "Female",
    "M": "Male",
    "H": "Male",
    "P": "People",
    "HM": "Male",
}

# ============================================================================
# COUNTRY CODES: Valid codes extracted from filename
# ============================================================================
COUNTRY_CODES = [
    "MX", "PE", "CL", "CO", "BR", "PY", "TT", "JM", "CY", "EC",
    "VI", "SV", "BB", "BS", "GY", "BM", "DO", "VE", "PA", "HN",
    "CR", "NI", "GT", "BO", "UY",
]

# ============================================================================
# MONTH MAPPING: Month number to abbreviation
# ============================================================================
MONTH_MAP = {
    1: "JAN", 2: "FEB", 3: "MAR", 4: "APR", 5: "MAY", 6: "JUN",
    7: "JUL", 8: "AUG", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC",
}

# ============================================================================
# PLATFORM CONFIGURATION
# ============================================================================
PLATFORM_CONFIG = {
    "DV360": {
        "prefix": "DV",
        "levels": ["Campaign", "Insertion Order", "Line Item", "Ad Group"],
        "uses_plan_level": False,
    },
    "Meta": {
        "prefix": "M",
        "levels": ["Campaign", "Ad Group"],
        "uses_plan_level": True,
    },
    "TikTok": {
        "prefix": "TK",
        "levels": ["Campaign", "Ad Group"],
        "uses_plan_level": True,
    },
    "Pinterest": {
        "prefix": "P",
        "levels": ["Campaign", "Ad Group"],
        "uses_plan_level": True,
    },
    "Google Ads": {
        "prefix": "S",
        "levels": ["Campaign", "Ad Group"],
        "uses_plan_level": True,
    },
    "Amazon Prime": {
        "prefix": "A",
        "levels": ["Campaign", "Ad Group"],
        "uses_plan_level": True,
    },
}

# ============================================================================
# PLATFORM ALIASES: Normalize CM values to Alfred platform catalog
# ============================================================================
PLATFORM_ALIASES = {
    "facebook": "Meta",
    "instagram": "Meta",
    "messenger": "Meta",
    "facebook/instagram": "Meta",
}

# ============================================================================
# TYPE OPTIONS: Valid values per (Platform, Level) combination
# ============================================================================
TYPE_OPTIONS = {
    ("DV360", "Campaign"): ["DV360"],
    ("DV360", "Insertion Order"): ["Youtube", "Programmatic", "PMP Guaranteed", "PMP Non Guaranteed", "Pause Ads", "Sponsorship Ads", "Lineups", "YT Shorts", "Masthead"],
    ("DV360", "Line Item"): ["Skip", "Non-Skip", "Bumper", "OX Display", "OX Video"],
    ("DV360", "Ad Group"): ["Skip", "Non-Skip", "Bumper", "OX Display", "OX Video", "YT Shorts"],
    ("Meta", "Campaign"): ["Meta"],
    ("Meta", "Ad Group"): ["NA"],
    ("TikTok", "Campaign"): ["TikTok", "TikTok Search", "TikTok Shop"],
    ("TikTok", "Ad Group"): ["Top View", "Top Feed", "TikTok Search", "TikTok Shop", "NA"],
    ("Pinterest", "Campaign"): ["Pinterest"],
    ("Pinterest", "Ad Group"): ["NA"],
    ("Google Ads", "Campaign"): ["Google Ads", "Google Search"],
    ("Google Ads", "Ad Group"): ["Google Search", "NA"],
    ("Amazon Prime", "Campaign"): ["Amazon Prime"],
    ("Amazon Prime", "Ad Group"): ["NA"],
}

# ============================================================================
# STATUS & IMP_STATUS OPTIONS
# ============================================================================
STATUS_OPTIONS = ["On", "Off"]
IMP_STATUS_OPTIONS = ["Implemented", "Pending", "Manual Imp."]
BUDGET_TYPE_OPTIONS = {
    "Meta": ["Standard", "Advantage"],
    "TikTok": ["Standard", "Advantage"],
}

# ============================================================================
# BID TYPE OPTIMIZATION OPTIONS: By (Platform, Campaign Goal / Type)
# Exact values from ALFRED spec - case sensitive
# ============================================================================
BID_TYPE_OPTIONS = {
    ("Meta", "Video Views"): [
        "Maximize ThruPlay views",
        "Maximize 2-second continuous video plays",
    ],
    ("Meta", "Site Traffic"): [
        "Maximize number of impressions",
        "Maximize number of link clicks",
        "Maximize daily unique reach",
        "Maximize number of landing page views",
        "Maximize number of conversations",
    ],
    ("Meta", "Reach"): [
        "Maximize reach of ads",
        "Maximize number of impressions",
        "Maximize ThruPlay views",
        "Maximize 2-second continuous video plays",
        "Maximize ad recall lift",
    ],
    ("DV360", "Youtube"): [
        "Control bid and budget at the line item level",
        "Maximize viewable impressions",
        "Maximize viewable for at least 10 seconds",
        "Maximize completed in-view and audible",
        "Maximize custom value / cost",
        "Maximize reach",
    ],
    ("DV360", "Non_Skip"): [
        "Fixed",
    ],
    ("DV360", "Skip"): [
        "Fixed",
    ],
    ("DV360", "PMP_Non_Guaranteed"): [
        "Maximize viewable impressions",
        "Maximize viewable for at least 10 seconds",
        "Maximize completed in-view and audible",
        "Maximize custom value/cost",
        "Maximize reach",
    ],
    ("DV360", "Bumper"): [
        "Fixed",
    ],
    ("TikTok", "Video Views"): [
        "6-second views (Focused view)",
        "15-second views (Focused view)",
    ],
    ("TikTok", "Reach"): [
        "Reach",
    ],
}

ALL_BID_TYPE_OPTIONS = list(set(
    opt for options in BID_TYPE_OPTIONS.values() for opt in options
))

# ============================================================================
# PRICE TYPE (Fixed for now, may vary by Platform in future)
# ============================================================================
PRICE_TYPE = "Dynamic"
