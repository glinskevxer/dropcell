"""Finding the readings that describe the cell rather than the pipe.

The half cell has to make contact with damp soil. On a frozen field, on a road
crossing, on gravel, it sometimes does not, and the meter then reads the
resistance of the contact instead of the potential of the pipe. It shows up as
one or two readings that jump sharply positive and come straight back, and it is
indistinguishable from a genuine short defect if you only look at one trace.

What separates them is that a contact problem moves the on and the off reading
together, because both are measured through the same bad contact, while a real
bare spot changes the gap between them. So the test is on the pair, not on the
value: a step whose off potential departs from its neighbours while the IR drop
stays where it was is the cell's fault, not the pipe's.

Nothing here deletes anything. A suspect step is reported so a human can decide,
and the filtered survey is a copy. A tool that quietly drops readings it did not
like is a tool that can hide the finding the whole survey was paid for.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from dropcell.errors import ValidationError
from dropcell.survey.cis import CisPoint, CisSurvey

DEFAULT_WINDOW = 5
DEFAULT_DEPARTURE_MV = 150.0
DEFAULT_IR_TOLERANCE_MV = 40.0


@dataclass(frozen=True)
class Spike:
    """One step that looks like a contact problem rather than a reading."""

    index: int
    point: CisPoint
    local_median_off_mv: float
    departure_mv: float
    ir_change_mv: float

    @property
    def station_m(self) -> float:
        """Where along the line the suspect step is."""
        return self.point.station.metres


def _window_values(values: list[float | None], index: int, window: int) -> list[float]:
    half = window // 2
    low = max(0, index - half)
    high = min(len(values), index + half + 1)
    return [
        value
        for position, value in enumerate(values[low:high], start=low)
        if position != index and value is not None
    ]


def find_spikes(
    survey: CisSurvey,
    *,
    window: int = DEFAULT_WINDOW,
    departure_mv: float = DEFAULT_DEPARTURE_MV,
    ir_tolerance_mv: float = DEFAULT_IR_TOLERANCE_MV,
) -> list[Spike]:
    """Report the steps whose readings look like poor cell contact."""
    if window < 3 or window % 2 == 0:
        raise ValidationError("the window has to be odd and at least three", window=window)
    if departure_mv <= 0:
        raise ValidationError("the departure has to be positive", departure_mv=departure_mv)
    offs: list[float | None] = [point.off_mv for point in survey.points]
    drops: list[float | None] = [point.ir_drop_mv for point in survey.points]
    found: list[Spike] = []
    for index, point in enumerate(survey.points):
        if point.off_mv is None or point.ir_drop_mv is None:
            continue
        neighbours = _window_values(offs, index, window)
        drop_neighbours = _window_values(drops, index, window)
        if len(neighbours) < 2 or len(drop_neighbours) < 2:
            continue
        median_off = statistics.median(neighbours)
        median_drop = statistics.median(drop_neighbours)
        departure = point.off_mv - median_off
        ir_change = point.ir_drop_mv - median_drop
        if departure > departure_mv and abs(ir_change) <= ir_tolerance_mv:
            found.append(
                Spike(
                    index=index,
                    point=point,
                    local_median_off_mv=median_off,
                    departure_mv=departure,
                    ir_change_mv=ir_change,
                )
            )
    return found


def without_spikes(survey: CisSurvey, spikes: list[Spike]) -> CisSurvey:
    """A copy of the survey with the named steps taken out."""
    drop = {spike.index for spike in spikes}
    kept = tuple(point for index, point in enumerate(survey.points) if index not in drop)
    if len(kept) < 2:
        raise ValidationError(
            "removing those steps leaves nothing to walk",
            kept=len(kept),
            removed=len(drop),
        )
    return CisSurvey(
        line_code=survey.line_code,
        taken_on=survey.taken_on,
        points=kept,
        nominal_interval_m=survey.nominal_interval_m,
        technician=survey.technician,
        direction=survey.direction,
    )
