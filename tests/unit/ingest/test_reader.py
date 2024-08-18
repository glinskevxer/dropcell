from __future__ import annotations

from pathlib import Path

import pytest

from dropcell.errors import IngestError
from dropcell.ingest.mapping import ColumnMapping, FieldType, MappingProfile
from dropcell.ingest.reader import content_hash, read_file, read_text
from dropcell.stationing import Convention

PROFILE = MappingProfile(
    name="acme_cis",
    columns=(
        ColumnMapping("station", FieldType.STATION, ("Station", "Chainage")),
        ColumnMapping("on_mv", FieldType.POTENTIAL, ("P/S On",)),
        ColumnMapping("off_mv", FieldType.POTENTIAL, ("P/S Off",), required=False),
        ColumnMapping("remark", FieldType.TEXT, ("Remark",), required=False, default=""),
    ),
)

GOOD = """Station,P/S On,P/S Off,Remark
0+00.00,-1.120 V,-0.905 V,
0+02.50,-1.118 V,-0.902 V,gate
0+05.00,-1.130 V,-0.911 V,
"""


def test_a_clean_file_reads_every_row() -> None:
    result = read_text(GOOD, PROFILE)
    assert result.accepted == 3
    assert result.rejected == 0
    assert result.acceptance_rate == pytest.approx(1.0)


def test_values_come_back_in_their_canonical_units() -> None:
    row = read_text(GOOD, PROFILE).rows[0]
    assert row["on_mv"] == pytest.approx(-1120.0)
    assert row["off_mv"] == pytest.approx(-905.0)
    assert row["station"].metres == pytest.approx(0.0)


def test_a_metric_file_is_read_in_the_metric_convention() -> None:
    text = "Station,P/S On\n1+000.0,-1120\n"
    row = read_text(text, PROFILE, convention=Convention.METRIC).rows[0]
    assert row["station"].metres == pytest.approx(1000.0)


def test_an_empty_optional_cell_comes_back_as_nothing() -> None:
    text = "Station,P/S On,P/S Off\n0+00.00,-1120,\n"
    assert read_text(text, PROFILE).rows[0]["off_mv"] is None


def test_a_column_the_file_does_not_have_falls_back_to_its_default() -> None:
    text = "Station,P/S On\n0+00.00,-1120\n"
    assert read_text(text, PROFILE).rows[0]["remark"] == ""


def test_an_absent_optional_column_with_no_default_is_nothing() -> None:
    text = "Station,P/S On\n0+00.00,-1120\n"
    assert read_text(text, PROFILE).rows[0]["off_mv"] is None


def test_a_bad_row_is_set_aside_and_the_rest_go_through() -> None:
    text = "Station,P/S On\n0+00.00,-1120\n0+02.50,not a reading\n0+05.00,-1130\n"
    result = read_text(text, PROFILE)
    assert result.accepted == 2
    assert result.rejected == 1
    assert result.quarantine[0].row_number == 3


def test_a_quarantined_row_keeps_its_reasons_and_its_raw_text() -> None:
    text = "Station,P/S On\n0+02.50,not a reading\n"
    quarantined = read_text(text, PROFILE).quarantine[0]
    assert quarantined.raw == ("0+02.50", "not a reading")
    assert quarantined.errors[0].field_name == "on_mv"
    assert "on_mv" in quarantined.summary


def test_a_row_with_several_faults_reports_all_of_them() -> None:
    text = "Station,P/S On\nnot a station,not a reading\n"
    quarantined = read_text(text, PROFILE).quarantine[0]
    assert {item.field_name for item in quarantined.errors} == {"station", "on_mv"}


def test_an_empty_required_cell_is_a_fault() -> None:
    text = "Station,P/S On\n0+00.00,\n"
    quarantined = read_text(text, PROFILE).quarantine[0]
    assert "cannot be empty" in quarantined.errors[0].message


def test_a_short_row_is_a_fault_when_it_loses_a_required_column() -> None:
    text = "Station,P/S On\n0+00.00\n"
    quarantined = read_text(text, PROFILE).quarantine[0]
    assert "short of this column" in quarantined.errors[0].message


def test_a_short_row_that_only_loses_an_optional_column_is_fine() -> None:
    text = "Station,P/S On,P/S Off\n0+00.00,-1120\n"
    result = read_text(text, PROFILE)
    assert result.accepted == 1
    assert result.rows[0]["off_mv"] is None


def test_blank_lines_are_skipped_rather_than_quarantined() -> None:
    text = "Station,P/S On\n0+00.00,-1120\n\n0+05.00,-1130\n"
    result = read_text(text, PROFILE)
    assert result.accepted == 2
    assert result.rejected == 0


def test_a_file_with_no_rows_at_all_is_not_an_error() -> None:
    result = read_text("Station,P/S On\n", PROFILE)
    assert result.total == 0
    assert result.acceptance_rate == pytest.approx(1.0)


def test_a_file_with_nothing_in_it_is_an_error() -> None:
    with pytest.raises(IngestError):
        read_text("", PROFILE)


def test_a_missing_required_column_stops_the_whole_import() -> None:
    with pytest.raises(IngestError):
        read_text("Chainage,Remark\n0+00.00,gate\n", PROFILE)


def test_leading_junk_rows_can_be_skipped() -> None:
    profile = MappingProfile(name="with_banner", columns=PROFILE.columns, skip_rows=2)
    text = "ACME Surveys Ltd\nJob 4417\nStation,P/S On\n0+00.00,-1120\n"
    result = read_text(text, profile)
    assert result.accepted == 1
    assert result.quarantine == ()


def test_row_numbers_account_for_the_skipped_rows() -> None:
    profile = MappingProfile(name="with_banner", columns=PROFILE.columns, skip_rows=2)
    text = "ACME Surveys Ltd\nJob 4417\nStation,P/S On\n0+00.00,bad\n"
    assert read_text(text, profile).quarantine[0].row_number == 4


def test_a_tab_separated_file_is_read_with_its_own_delimiter() -> None:
    profile = MappingProfile(name="tabbed", columns=PROFILE.columns, delimiter="\t")
    result = read_text("Station\tP/S On\n0+00.00\t-1120\n", profile)
    assert result.accepted == 1


def test_the_content_hash_is_of_the_bytes_that_arrived() -> None:
    result = read_text(GOOD, PROFILE)
    assert result.content_hash == content_hash(GOOD.encode("utf-8"))


def test_the_same_bytes_hash_the_same_and_different_bytes_do_not() -> None:
    assert read_text(GOOD, PROFILE).content_hash == read_text(GOOD, PROFILE).content_hash
    changed = GOOD.replace("-1.120 V", "-1.121 V")
    assert read_text(changed, PROFILE).content_hash != read_text(GOOD, PROFILE).content_hash


def test_a_result_can_be_held_to_a_minimum_acceptance() -> None:
    text = "Station,P/S On\n0+00.00,-1120\n0+02.50,bad\n"
    result = read_text(text, PROFILE)
    result.require_acceptance(0.5)
    with pytest.raises(IngestError) as caught:
        result.require_acceptance(0.9)
    assert caught.value.detail["rejected"] == 1


def test_reading_from_disk_carries_the_file_name(tmp_path: Path) -> None:
    target = tmp_path / "cis-2025-03.csv"
    target.write_text(GOOD, encoding="utf-8")
    result = read_file(target, PROFILE)
    assert result.source == "cis-2025-03.csv"
    assert result.accepted == 3


def test_reading_a_file_that_is_not_there_is_refused(tmp_path: Path) -> None:
    with pytest.raises(IngestError):
        read_file(tmp_path / "missing.csv", PROFILE)
