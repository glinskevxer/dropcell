from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ConflictError, NotFoundError
from dropcell.model.line import Line
from dropcell.store.database import Database
from dropcell.store.depolarisation import DepolarisationRepository
from dropcell.store.lines import LineRepository
from dropcell.survey.depolarisation import DepolarisationPoint, DepolarisationSurvey

OFF_AT = dt.datetime(2025, 3, 14, 6, 0)


@pytest.fixture
def register(database: Database, line: Line) -> Database:
    LineRepository(database).add(line)
    return database


def survey(**overrides: object) -> DepolarisationSurvey:
    kwargs: dict[str, object] = {
        "line_code": "AL-2",
        "switched_off_at": OFF_AT,
        "read_back_at": OFF_AT + dt.timedelta(hours=24),
        "points": (
            DepolarisationPoint(test_point_code="TP-1", off_mv=-905.0, depolarised_mv=-780.0),
            DepolarisationPoint(test_point_code="TP-2", off_mv=-900.0, depolarised_mv=None),
        ),
        "technician": "R Ellis",
    }
    kwargs.update(overrides)
    return DepolarisationSurvey(**kwargs)  # type: ignore[arg-type]


def test_a_survey_survives_a_round_trip(register: Database) -> None:
    repository = DepolarisationRepository(register)
    survey_id = repository.add(survey())
    stored = repository.get(survey_id)
    assert stored == survey()
    assert stored.hours_off == pytest.approx(24.0)


def test_a_point_read_once_comes_back_with_no_second_reading(
    register: Database,
) -> None:
    repository = DepolarisationRepository(register)
    stored = repository.get(repository.add(survey()))
    assert stored.missed_on_the_second_pass == ("TP-2",)


def test_a_survey_on_a_line_that_is_not_there_is_refused(
    database: Database,
) -> None:
    with pytest.raises(ConflictError):
        DepolarisationRepository(database).add(survey())


def test_two_surveys_against_one_switch_off_are_refused(register: Database) -> None:
    repository = DepolarisationRepository(register)
    repository.add(survey())
    with pytest.raises(ConflictError):
        repository.add(survey())


def test_another_switch_off_on_the_same_day_is_fine(register: Database) -> None:
    repository = DepolarisationRepository(register)
    repository.add(survey())
    repository.add(
        survey(
            switched_off_at=OFF_AT + dt.timedelta(hours=1),
            read_back_at=OFF_AT + dt.timedelta(hours=26),
        )
    )
    assert repository.count() == 2


def test_surveys_come_back_oldest_first(register: Database) -> None:
    repository = DepolarisationRepository(register)
    repository.add(
        survey(
            switched_off_at=dt.datetime(2024, 3, 14, 6, 0),
            read_back_at=dt.datetime(2024, 3, 15, 6, 0),
        )
    )
    repository.add(survey())
    dates = [item.switched_off_at for item in repository.for_line("AL-2")]
    assert dates == sorted(dates)


def test_the_latest_survey_is_the_most_recent_switch_off(register: Database) -> None:
    repository = DepolarisationRepository(register)
    repository.add(
        survey(
            switched_off_at=dt.datetime(2024, 3, 14, 6, 0),
            read_back_at=dt.datetime(2024, 3, 15, 6, 0),
        )
    )
    repository.add(survey())
    latest = repository.latest("AL-2")
    assert latest is not None
    assert latest.switched_off_at == OFF_AT


def test_a_line_with_no_surveys_has_no_latest(register: Database) -> None:
    assert DepolarisationRepository(register).latest("AL-2") is None


def test_a_survey_number_that_is_not_there_is_refused(register: Database) -> None:
    with pytest.raises(NotFoundError):
        DepolarisationRepository(register).get(99)


def test_the_stored_survey_still_scores_itself(register: Database) -> None:
    repository = DepolarisationRepository(register)
    stored = repository.get(repository.add(survey()))
    assert stored.share_meeting() == pytest.approx(1.0)
    assert stored.problems() == ("1 posts were not read on the second pass",)


def test_deleting_a_line_takes_its_surveys_and_their_points(
    register: Database,
) -> None:
    repository = DepolarisationRepository(register)
    repository.add(survey())
    LineRepository(register).delete("AL-2")
    assert repository.count() == 0
    assert register.scalar("SELECT count(*) FROM depolarisation_point") == 0
