"""Reading a sounding at the depth the pipe is actually buried at.

Two numbers describe the ground under a segment and they are arrived at
completely differently. One is ``soil_resistivity_ohm_m`` on the segment, typed
in by whoever set the segment up, usually off a design document and usually the
bulk figure from a wide pin spacing. The other is a four pin sounding, which is
a set of numbers at a point on a day and which Barnes turns into layers.

Nothing has ever compared them, and the comparison is worth making, because the
bulk figure and the layer the pipe is lying in are not the same measurement and
on layered ground they are not close. A sounding at four metre spacing averages
four metres of ground. If the top two metres are dry sand and the pipe is at
one metre down in that sand, the bulk figure bands benign and it is right about
the bulk. The pipe is in the sand.

That error runs both ways and only one direction matters. A segment whose file
says the ground is worse than it is gets surveyed more often than it needs,
which costs money and finds nothing. A segment whose file says the ground is
better than it is gets surveyed less often than it needs, and the first anyone
hears of it is a leak. So understatement is called out by name here and
overstatement is reported and left alone.

The depth is the part that is easy to get wrong. ``survey soil`` reads every
sounding on a line at one depth off a flag, which is fine for a first look and
wrong for a road crossing at two and a half metres sitting in the same line as
farmland at one. Each segment carries its own depth of cover and that is the
depth its ground gets read at here.

Nothing in here writes back to the segment. The soundings module already says
why: turning a set of numbers at a point into the one number a criterion needs
is a decision somebody makes with a depth in mind, and a disagreement is
evidence for that decision rather than the decision itself.
"""

from __future__ import annotations

from dataclasses import dataclass

from dropcell.model.enums import SoilCorrosivity
from dropcell.model.segment import Segment
from dropcell.soil import CORROSIVITY_BANDS, classify_corrosivity
from dropcell.stationing import Station
from dropcell.store.soundings import Sounding

BAND_ORDER: list[SoilCorrosivity] = [band for _, band in CORROSIVITY_BANDS] + [
    SoilCorrosivity.BENIGN
]
"""Bands worst first.

Read off the same table the classifier uses rather than written out again, so
inserting a band in ``soil`` cannot leave a second ordering here disagreeing
with it.
"""

WIDE_MARGIN = 2.0


def _severity(band: SoilCorrosivity) -> int:
    """How bad a band is, so two bands can be compared. Higher is worse."""
    return len(BAND_ORDER) - BAND_ORDER.index(band)


def _midpoint(segment: Segment) -> Station:
    """The middle of a segment, which is where it gets measured from."""
    return Station((segment.extent.start.metres + segment.extent.end.metres) / 2.0)


@dataclass(frozen=True)
class GroundAt:
    """One segment's ground, as filed and as measured at its own depth of cover."""

    segment_code: str
    depth_of_cover_m: float
    measured_ohm_m: float
    sounding_id: int | None
    distance_m: float
    filed_ohm_m: float | None = None

    @property
    def measured_band(self) -> SoilCorrosivity:
        """The band the ground at pipe depth actually falls in."""
        return classify_corrosivity(self.measured_ohm_m)

    @property
    def filed_band(self) -> SoilCorrosivity | None:
        """The band the segment's own figure falls in, when it carries one."""
        if self.filed_ohm_m is None:
            return None
        return classify_corrosivity(self.filed_ohm_m)

    @property
    def has_filed_figure(self) -> bool:
        """Whether there is anything to compare the sounding against."""
        return self.filed_ohm_m is not None

    @property
    def bands_agree(self) -> bool:
        """Whether both routes to a band land on the same one.

        A segment with no filed figure is not a disagreement. It is a segment
        nobody has typed a number into, which is a different thing and is
        reported as its own state.
        """
        filed = self.filed_band
        return filed is None or filed is self.measured_band

    @property
    def understates(self) -> bool:
        """Whether the file reads kinder than the ground at pipe depth."""
        filed = self.filed_band
        if filed is None:
            return False
        return _severity(self.measured_band) > _severity(filed)

    @property
    def overstates(self) -> bool:
        """Whether the file reads harsher than the ground at pipe depth."""
        filed = self.filed_band
        if filed is None:
            return False
        return _severity(self.measured_band) < _severity(filed)

    @property
    def ratio(self) -> float | None:
        """Filed over measured, which says how far apart the two numbers are."""
        if self.filed_ohm_m is None:
            return None
        return self.filed_ohm_m / self.measured_ohm_m

    @property
    def is_far_off(self) -> bool:
        """Whether the two numbers differ by more than the stated margin.

        Bands can agree while the numbers are a long way apart, and this is
        only asked once they do agree, so it is the last thing that can make a
        matching pair interesting.

        In practice it fires at the two open ended bands and almost nowhere
        else, which is deliberate rather than a gap. The bands in between are
        each about a factor of two wide, so two numbers inside one of them are
        already known to be close. Benign runs from a hundred ohm metres
        upwards and says nothing about how far up, and that is exactly the case
        where the band has stopped carrying information and the numbers still
        do.
        """
        ratio = self.ratio
        if ratio is None:
            return False
        return ratio > WIDE_MARGIN or ratio < 1.0 / WIDE_MARGIN

    @property
    def verdict(self) -> str:
        """A word for the comparison."""
        if not self.has_filed_figure:
            return "not filed"
        if self.understates:
            return "understated"
        if self.overstates:
            return "overstated"
        if self.is_far_off:
            return "same band, wide"
        return "agrees"

    def explain(self) -> str:
        """One line saying what was compared and what came out."""
        head = (
            f"{self.segment_code}: ground at {self.depth_of_cover_m:.1f} m reads "
            f"{self.measured_ohm_m:.0f} ohm m ({self.measured_band})"
        )
        if self.filed_ohm_m is None:
            return f"{head}, nothing filed against it"
        return (
            f"{head}, filed as {self.filed_ohm_m:.0f} ohm m ({self.filed_band}), {self.verdict}"
        )


def assess_ground(segment: Segment, sounding: Sounding) -> GroundAt:
    """Read one sounding at one segment's depth of cover and compare."""
    midpoint = _midpoint(segment)
    return GroundAt(
        segment_code=segment.code,
        depth_of_cover_m=segment.depth_of_cover_m,
        measured_ohm_m=sounding.at_depth(segment.depth_of_cover_m),
        sounding_id=sounding.sounding_id,
        distance_m=abs(sounding.station.metres - midpoint.metres),
        filed_ohm_m=segment.soil_resistivity_ohm_m,
    )


def assess_line(segments: list[Segment], soundings: list[Sounding]) -> list[GroundAt]:
    """Compare every segment against whichever sounding was taken nearest to it.

    A segment with no sounding anywhere on the line is left out rather than
    reported as agreeing with nothing.
    """
    if not soundings:
        return []
    results: list[GroundAt] = []
    for segment in segments:
        midpoint = _midpoint(segment)
        nearest = min(soundings, key=lambda item: abs(item.station.metres - midpoint.metres))
        results.append(assess_ground(segment, nearest))
    return results


def understated(results: list[GroundAt]) -> list[GroundAt]:
    """The segments whose filed figure reads kinder than the ground does.

    These are the ones worth acting on. Ordered by how far out they are, so the
    segment filed as benign and measuring corrosive comes before the one that
    slipped a single band.
    """
    wrong = [item for item in results if item.understates]
    return sorted(
        wrong,
        key=lambda item: (
            -(_severity(item.measured_band) - _severity(item.filed_band or item.measured_band)),
            item.segment_code,
        ),
    )
