from __future__ import annotations

from dropcell.ingest.profiles import CIS_PROFILE, get_profile
from dropcell.ingest.validate import best_match, headers_of, identify, try_profile

CIS = "Station,P/S On,P/S Off\n0+00.00,-1120,-905\n0+05.00,-1118,-902\n"
ANNUAL = "Test Post,Date,On,Off\nTP-114,2025-03-14,-1120,-905\n"


def test_the_headers_of_a_file_are_read_off_the_first_row() -> None:
    assert headers_of(CIS, CIS_PROFILE) == ["Station", "P/S On", "P/S Off"]


def test_skipped_rows_are_stepped_over_before_the_header() -> None:
    from dropcell.ingest.mapping import MappingProfile

    profile = MappingProfile(name="banner", columns=CIS_PROFILE.columns, skip_rows=2)
    text = "ACME Surveys\nJob 4417\n" + CIS
    assert headers_of(text, profile) == ["Station", "P/S On", "P/S Off"]


def test_an_empty_file_has_no_headers() -> None:
    assert headers_of("", CIS_PROFILE) == []


def test_a_matching_profile_reads_the_file() -> None:
    match = try_profile(CIS, CIS_PROFILE)
    assert match.readable
    assert match.accepted == 2
    assert match.rejected == 0
    assert match.missing == ()


def test_the_columns_it_matched_are_named() -> None:
    match = try_profile(CIS, CIS_PROFILE)
    assert ("Station", "station") in match.matched
    assert ("P/S Off", "off_mv") in match.matched


def test_a_header_nothing_matched_is_named() -> None:
    text = "Station,P/S On,Operator Notes\n0+00.00,-1120,x\n"
    match = try_profile(text, CIS_PROFILE)
    assert match.unmatched_headers == ("Operator Notes",)


def test_a_profile_that_cannot_read_the_file_names_what_is_missing() -> None:
    match = try_profile(ANNUAL, CIS_PROFILE)
    assert not match.readable
    assert "on_mv" in match.missing or "station" in match.missing


def test_a_file_with_bad_rows_still_reads_and_counts_them() -> None:
    text = CIS + "0+10.00,rubbish,\n"
    match = try_profile(text, CIS_PROFILE)
    assert match.readable
    assert match.rejected == 1


def test_identify_reports_every_profile() -> None:
    from dropcell.ingest.profiles import PROFILES

    assert len(identify(CIS)) == len(PROFILES)


def test_the_right_profile_comes_first() -> None:
    assert identify(CIS)[0].profile == "cis"
    assert identify(ANNUAL)[0].profile == "annual"


def test_the_best_match_is_the_one_that_reads_the_most() -> None:
    match = best_match(CIS)
    assert match is not None
    assert match.profile == "cis"
    assert match.accepted == 2


def test_a_file_no_profile_can_read_has_no_best_match() -> None:
    assert best_match("Colour,Shape\nred,round\n") is None


def test_an_empty_file_has_no_best_match() -> None:
    assert best_match("") is None


def test_the_scores_order_readable_profiles_above_unreadable_ones() -> None:
    matches = identify(CIS)
    readable = [match.readable for match in matches]
    assert readable == sorted(readable, reverse=True)


def test_nothing_here_needs_a_register() -> None:
    match = try_profile(CIS, get_profile("cis"))
    assert match.accepted == 2
