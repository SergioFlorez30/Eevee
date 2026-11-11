import pytest

from tests.conftest import cm_row, run_transform


def source(platform, path, budget, frequency, **extra):
    return cm_row(platform, path, **{
        "Billable Budget": str(budget), "Total Budget": str(budget),
        "Frequency": str(frequency), **extra,
    })


@pytest.mark.parametrize("platform", ["TikTok", "Meta", "DV360"])
@pytest.mark.parametrize("reverse", [False, True])
def test_zero_copy_removed_before_ids_and_generated_children(platform, reverse):
    path = "Hair Care -> CMP_1 -> IO1_a -> LI1_a" if platform == "DV360" else "Hair Care -> CMP_1 -> ADG1_a"
    copies = [
        source(platform, path, 0, 0, **{"Publisher ID": "A"}),
        source(platform, path, 245000, 4, **{"Publisher ID": "B"}),
    ]
    if reverse:
        copies.reverse()
    rows, _ = run_transform(copies)
    target = [r for r in rows if r["CAMPAIGN_TAXO"] == path.split(" -> ")[-1]]
    assert len(target) == 1
    assert target[0]["BUDGET"] == 245000
    assert target[0]["TOTAL_BUDGET"] == 245000
    assert target[0]["FREQUENCY"] == "4x7"
    assert len(rows) == (4 if platform == "DV360" else 1)


def test_herbal_regression_four_ad_groups_and_consecutive_ids():
    rows = [source("TikTok", "Hair Care -> CMP_1", 490000, 8)]
    for code, frequency in [("ADG08CCC", 4), ("ADG08F70", 4)]:
        path = f"Hair Care -> CMP_1 -> {code}_DEMO"
        rows += [source("TikTok", path, 0, 0), source("TikTok", path, 245000, frequency)]
    rows += [source("TikTok", "Hair Care -> CMP_2", 490000, 16)]
    for code, frequency in [("ADG08F73", 4), ("ADG08F74", 12)]:
        path = f"Hair Care -> CMP_2 -> {code}_DEMO"
        rows += [source("TikTok", path, 245000, frequency), source("TikTok", path, 0, 0)]
    output, _ = run_transform(rows)
    assert [r["ID"] for r in output] == ["TK1", "TK1-1", "TK1-2", "TK2", "TK2-1", "TK2-2"]
    assert [r["FREQUENCY"] for r in output] == ["8x7", "4x7", "4x7", "16x7", "4x7", "12x7"]


@pytest.mark.parametrize("difference", [
    {"Brand": "Different"}, {"Target Audience": "Male 18+"},
    {"Start Date": "02/01/2026"}, {"Allocated Coupons (Planned)": "10"},
])
def test_other_conflicts_are_not_removed(difference):
    rows, _ = run_transform([
        source("TikTok", "CMP_1", 0, 0),
        source("TikTok", "CMP_1", 245000, 4, **difference),
    ])
    assert len(rows) == 2


def test_multiple_nonzero_alternatives_preserve_all_rows():
    rows, _ = run_transform([
        source("TikTok", "CMP_1", 0, 0),
        source("TikTok", "CMP_1", 245000, 4),
        source("TikTok", "CMP_1", 245000, 12),
    ])
    assert len(rows) == 3


def test_unique_zero_record_is_preserved():
    rows, _ = run_transform([source("TikTok", "CMP_1", 0, 0)])
    assert len(rows) == 1
    assert rows[0]["FREQUENCY"] == "0x7"
