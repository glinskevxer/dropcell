"""Storing a depolarisation survey, which is a switch off and everything read against it.

The switch off is the key. Two posts read on the same day against two different
switch offs are two surveys, and rolling them together produces decay figures
measured from different starting points, which is the one mistake that makes the
whole exercise worthless.

The line and the switch off are unique together for the same reason. A crew that
records a second survey against the same switch off has either split one survey
in two or is about to overwrite half of it.
"""

from __future__ import annotations

import datetime as dt

from dropcell.errors import NotFoundError
from dropcell.model.ids import normalise_code
from dropcell.store.database import Database
from dropcell.survey.depolarisation import DepolarisationPoint, DepolarisationSurvey


class DepolarisationRepository:
    """Every depolarisation survey in the register."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def add(self, survey: DepolarisationSurvey) -> int:
        """Store one survey and its points, and hand back its number."""
        with self.database.transaction():
            cursor = self.database.execute(
                "INSERT INTO depolarisation (line_code, switched_off_at, read_back_at,"
                " technician) VALUES (?, ?, ?, ?)",
                (
                    survey.line_code,
                    survey.switched_off_at.isoformat(timespec="seconds"),
                    survey.read_back_at.isoformat(timespec="seconds"),
                    survey.technician,
                ),
            )
            survey_id = int(cursor.lastrowid or 0)
            self.database.executemany(
                "INSERT INTO depolarisation_point (survey_id, test_point_code, off_mv,"
                " depolarised_mv, remark) VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        survey_id,
                        point.test_point_code,
                        point.off_mv,
                        point.depolarised_mv,
                        point.remark,
                    )
                    for point in survey.points
                ],
            )
        return survey_id

    def get(self, survey_id: int) -> DepolarisationSurvey:
        """One survey by its number."""
        row = self.database.query_one(
            "SELECT id, line_code, switched_off_at, read_back_at, technician"
            " FROM depolarisation WHERE id = ?",
            (survey_id,),
        )
        if row is None:
            raise NotFoundError("no depolarisation survey with that number", id=survey_id)
        return self._build(row)

    def for_line(self, line_code: str) -> list[DepolarisationSurvey]:
        """Every survey on one line, oldest first."""
        rows = self.database.query(
            "SELECT id, line_code, switched_off_at, read_back_at, technician"
            " FROM depolarisation WHERE line_code = ? ORDER BY switched_off_at",
            (normalise_code(line_code, kind="line code"),),
        )
        return [self._build(row) for row in rows]

    def latest(self, line_code: str) -> DepolarisationSurvey | None:
        """The most recent survey on one line."""
        found = self.for_line(line_code)
        return found[-1] if found else None

    def count(self) -> int:
        """How many surveys the register holds."""
        return int(self.database.scalar("SELECT count(*) FROM depolarisation") or 0)

    def _build(self, row: object) -> DepolarisationSurvey:
        survey_id = int(row["id"])  # type: ignore[index]
        points = self.database.query(
            "SELECT test_point_code, off_mv, depolarised_mv, remark"
            " FROM depolarisation_point WHERE survey_id = ? ORDER BY test_point_code",
            (survey_id,),
        )
        return DepolarisationSurvey(
            line_code=str(row["line_code"]),  # type: ignore[index]
            switched_off_at=dt.datetime.fromisoformat(str(row["switched_off_at"])),  # type: ignore[index]
            read_back_at=dt.datetime.fromisoformat(str(row["read_back_at"])),  # type: ignore[index]
            points=tuple(
                DepolarisationPoint(
                    test_point_code=str(item["test_point_code"]),
                    off_mv=float(item["off_mv"]),
                    depolarised_mv=(
                        None
                        if item["depolarised_mv"] is None
                        else float(item["depolarised_mv"])
                    ),
                    remark=str(item["remark"]),
                )
                for item in points
            ),
            technician=str(row["technician"]),  # type: ignore[index]
        )
