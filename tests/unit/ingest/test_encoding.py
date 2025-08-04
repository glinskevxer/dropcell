from __future__ import annotations

from pathlib import Path

import pytest

from dropcell.ingest.mapping import ColumnMapping, FieldType, MappingProfile
from dropcell.ingest.reader import decode, read_file

PROFILE = MappingProfile(
    name="names",
    columns=(
        ColumnMapping("station", FieldType.STATION, ("Station",)),
        ColumnMapping("on_mv", FieldType.POTENTIAL, ("On",)),
        ColumnMapping("technician", FieldType.TEXT, ("By",), required=False),
    ),
)

ROWS = "Station,On,By\n0+00.00,-1120,{name}\n"


def test_plain_utf8_reads_as_itself() -> None:
    text, used = decode(b"abc", "utf-8")
    assert text == "abc"
    assert used == "utf-8"


def test_a_byte_order_mark_is_stripped() -> None:
    text, used = decode("Station".encode("utf-8-sig"), "utf-8")
    assert text == "Station"
    assert used == "utf-8-sig"


def test_a_windows_export_is_read_rather_than_mangled() -> None:
    payload = ROWS.format(name="R Ellis – relief").encode("cp1252")
    text, used = decode(payload, "utf-8")
    assert used in {"cp1252", "latin-1"}
    assert "�" not in text


def test_the_declared_encoding_is_tried_first() -> None:
    payload = "café".encode("cp1252")
    text, used = decode(payload, "cp1252")
    assert used == "cp1252"
    assert text == "café"


def test_something_nothing_can_read_falls_back_to_replacement() -> None:
    payload = b"\x80\x81" + b"abc"
    text, used = decode(payload, "utf-8")
    assert isinstance(text, str)
    assert used in {"cp1252", "latin-1", "utf-8 with replacements"}


def test_a_file_records_the_encoding_it_needed(tmp_path: Path) -> None:
    target = tmp_path / "windows.csv"
    target.write_bytes(ROWS.format(name="R Ellis").encode("cp1252"))
    result = read_file(target, PROFILE)
    assert result.accepted == 1
    assert result.encoding in {"utf-8", "cp1252", "latin-1"}


def test_a_utf8_file_does_not_need_a_fallback(tmp_path: Path) -> None:
    target = tmp_path / "clean.csv"
    target.write_text(ROWS.format(name="R Ellis"), encoding="utf-8")
    result = read_file(target, PROFILE)
    assert not result.needed_a_fallback


def test_a_windows_file_says_it_needed_one(tmp_path: Path) -> None:
    target = tmp_path / "windows.csv"
    target.write_bytes(ROWS.format(name="José – relief").encode("cp1252"))
    result = read_file(target, PROFILE)
    assert result.needed_a_fallback
    assert "José" in result.rows[0]["technician"]


def test_the_content_hash_is_still_of_the_bytes(tmp_path: Path) -> None:
    from dropcell.ingest.reader import content_hash

    payload = ROWS.format(name="R Ellis").encode("cp1252")
    target = tmp_path / "windows.csv"
    target.write_bytes(payload)
    assert read_file(target, PROFILE).content_hash == content_hash(payload)


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "cp1252", "latin-1"])
def test_the_same_survey_reads_the_same_however_it_was_saved(
    tmp_path: Path, encoding: str
) -> None:
    target = tmp_path / f"{encoding}.csv"
    target.write_bytes(ROWS.format(name="R Ellis").encode(encoding))
    result = read_file(target, PROFILE)
    assert result.rows[0]["technician"] == "R Ellis"
    assert result.rows[0]["on_mv"] == pytest.approx(-1120.0)
