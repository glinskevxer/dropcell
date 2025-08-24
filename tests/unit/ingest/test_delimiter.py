from __future__ import annotations

import pytest

from dropcell.ingest.mapping import ColumnMapping, FieldType, MappingProfile
from dropcell.ingest.reader import read_text, sniff_delimiter
from dropcell.ingest.validate import headers_of

PROFILE = MappingProfile(
    name="cis",
    columns=(
        ColumnMapping("station", FieldType.STATION, ("Station",)),
        ColumnMapping("on_mv", FieldType.POTENTIAL, ("On",)),
        ColumnMapping("off_mv", FieldType.POTENTIAL, ("Off",), required=False),
    ),
)


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("Station,On,Off", ","),
        ("Station;On;Off", ";"),
        ("Station\tOn\tOff", "\t"),
        ("Station|On|Off", "|"),
    ],
)
def test_the_separator_is_read_off_the_header(header: str, expected: str) -> None:
    assert sniff_delimiter(header) == expected


def test_the_declared_separator_wins_when_it_is_there() -> None:
    assert sniff_delimiter("Station;On,Off", declared=",") == ","


def test_a_header_with_no_separator_keeps_the_declared_one() -> None:
    assert sniff_delimiter("Station", declared=";") == ";"


def test_an_empty_file_keeps_the_declared_one() -> None:
    assert sniff_delimiter("", declared="\t") == "\t"


def test_a_semicolon_file_reads_without_a_profile_change() -> None:
    result = read_text("Station;On;Off\n0+00.00;-1120;-905\n", PROFILE)
    assert result.accepted == 1
    assert result.rows[0]["off_mv"] == pytest.approx(-905.0)
    assert result.delimiter == ";"


def test_a_tab_file_reads_too() -> None:
    result = read_text("Station\tOn\tOff\n0+00.00\t-1120\t-905\n", PROFILE)
    assert result.accepted == 1
    assert result.separated_by == "tabs"


def test_an_ordinary_comma_file_is_unchanged() -> None:
    result = read_text("Station,On,Off\n0+00.00,-1120,-905\n", PROFILE)
    assert result.accepted == 1
    assert result.separated_by == "commas"


def test_sniffing_can_be_switched_off() -> None:
    from dropcell.errors import IngestError

    with pytest.raises(IngestError):
        read_text("Station;On;Off\n0+00.00;-1120;-905\n", PROFILE, sniff=False)


def test_a_comma_inside_a_remark_does_not_confuse_a_semicolon_file() -> None:
    profile = MappingProfile(
        name="with_remark",
        columns=(
            *PROFILE.columns,
            ColumnMapping("remark", FieldType.TEXT, ("Remark",), required=False),
        ),
    )
    text = "Station;On;Off;Remark\n0+00.00;-1120;-905;gate, locked, dog\n"
    result = read_text(text, profile)
    assert result.accepted == 1
    assert result.rows[0]["remark"] == "gate, locked, dog"


def test_the_header_reader_sniffs_as_well() -> None:
    assert headers_of("Station;On;Off\n", PROFILE) == ["Station", "On", "Off"]


def test_a_profile_that_declares_tabs_still_reads_a_tab_file() -> None:
    profile = MappingProfile(name="tabbed", columns=PROFILE.columns, delimiter="\t")
    result = read_text("Station\tOn\n0+00.00\t-1120\n", profile)
    assert result.accepted == 1


def test_the_separator_has_a_word_for_it() -> None:
    assert read_text("Station|On\n0+00.00|-1120\n", PROFILE).separated_by == "pipes"
