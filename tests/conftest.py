import csv
import io
import sys
from io import BytesIO
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.transform import parse_csv, run, transform  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"

CM_HEADER = [
    "Platform", "Line Item", "Start Date", "End Date", "Brand", "Sub Brand",
    "Total Budget", "Billable Budget", "Target Audience", "Media Objective",
    "Initiative", "Cost Type", "Publisher", "Allocated Coupons (Planned)",
    "OU Planning Level",
]

DEFAULT_ROW = {
    "Start Date": "01/01/2026",
    "End Date": "31/01/2026",
    "Brand": "Oral-B",
    "Sub Brand": "Pro",
    "Total Budget": "100",
    "Billable Budget": "100",
    "Target Audience": "W_18-34",
    "Media Objective": "Awareness",
    "Initiative": "Launch",
    "Cost Type": "CPM",
    "Publisher": "",
    "Allocated Coupons (Planned)": "0",
    "OU Planning Level": "",
}


def cm_row(platform, line_item, **overrides):
    """Build a CM row; overrides use the exact CM column name."""
    row = dict(DEFAULT_ROW, Platform=platform)
    row["Line Item"] = line_item
    row.update(overrides)
    return row


def build_csv(rows, header=None):
    header = list(header or CM_HEADER)
    for row in rows:
        header += [key for key in row if key not in header]
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([row.get(col, "") for col in header])
    return buffer.getvalue()


def run_transform(rows, filename="Plan_MX.csv"):
    return transform(parse_csv(build_csv(rows)), filename)


def load_fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def summary(output_rows):
    return [(r["PLATFORM"], r["LEVEL"], r["ID"]) for r in output_rows]


@pytest.fixture
def excel_from():
    from openpyxl import load_workbook

    def _load(csv_text, filename="Plan_MX.csv"):
        result = run(csv_text, filename)
        assert result["excel_bytes"], result["errors"]
        return result, load_workbook(BytesIO(result["excel_bytes"]))

    return _load
