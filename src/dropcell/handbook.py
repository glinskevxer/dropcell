"""The handbook, kept in the package rather than in a file beside it.

A document in the repository is read by whoever cloned the repository. The
people who need this are running an installed command on a laptop in a depot,
and the only documentation they will ever see is the documentation the command
itself will print.

So it lives here, it is structured rather than one block of prose, and the
sections can be asked for by name. What it does not do is explain the domain.
Somebody running this is a CP technician and knows what an instant off potential
is; what they do not know is which of thirty commands produces the number their
manager asked for.
"""

from __future__ import annotations

from dataclasses import dataclass

from dropcell.errors import ValidationError


@dataclass(frozen=True)
class Section:
    """One part of the handbook."""

    key: str
    title: str
    body: str

    def render(self) -> str:
        """The section with its heading."""
        return f"{self.title}\n{'-' * len(self.title)}\n\n{self.body.strip()}\n"


SECTIONS: tuple[Section, ...] = (
    Section(
        key="start",
        title="Setting a register up",
        body="""
dropcell init                       make the register
dropcell line add ...               describe the pipe
dropcell segment add ...            cut it into segments
dropcell post add ...               every test post, with the leads it carries
dropcell rectifier add-bed ...      the anode bed first
dropcell rectifier add ...          then the unit that feeds it
dropcell plant add-casing ...       casings, crossings, bonds, joints
dropcell register check             find what the schema cannot

Nothing can be judged on a line with no segments, because the criterion is
chosen from the coating and the protection method, and both of those live on
the segment.
""",
    ),
    Section(
        key="year",
        title="The order of a year",
        body="""
dropcell import check FILE          what would happen, before anything happens
dropcell import annual FILE         the test post survey
dropcell rectifier check TAG ...    six times a year, or import rectifier
dropcell plant test-casing ...      the interference round
dropcell survey cis FILE            a close interval survey when one lands
dropcell survey dcvg FILE           a gradient survey, which produces a dig sheet
dropcell coupon import FILE         coupon readings, where there are coupons
dropcell report protection          how the line read
dropcell report compliance          what is overdue and what is coming
dropcell finding ...                work the exceptions through
dropcell report annual              the record for the file
""",
    ),
    Section(
        key="reading",
        title="Reading the reports",
        body="""
report protection splits the posts three ways and the third group is the one to
read first. A post that could not be judged is missing field work, not a passing
post and not a failing one.

report compliance counts asset and rule pairs, not visits. A rule has two
halves, a count per calendar year and a maximum interval, and a programme can
satisfy either one on its own while failing the other.

report coverage is over line length. A hundred percent protection over one
percent of the line is normal on a line with posts a mile apart, and it is what
this report exists to show.

plan trend fits a straight line through each post's history. It will not fit
fewer than three readings and it will not extrapolate past the horizon.

plan coating compares the current draw against what the coating should draw. It
is the only figure in here that describes the coating rather than the potential.
""",
    ),
    Section(
        key="groups",
        title="Which group a command is in",
        body="""
line, segment, post, rectifier, plant, coupon    describe and read the plant
import, survey                                   get files in
finding, work                                    what somebody has to do
note                                             what no column will hold
report                                           questions somebody has today
plan                                             questions asked once a quarter
register                                         the file itself

init, schema, settings, about, handbook          the tool itself
""",
    ),
    Section(
        key="units",
        title="Units and stationing",
        body="""
Every option that takes a measurement takes it with a unit.

A bare number in a potential column is millivolts. A bare number in a rectifier
output column is volts. Those two defaults disagree on purpose, because that is
what the instruments read.

A line is surveyed in feet or in metres and every station is printed back in
whichever it was. Inside the register everything is metres from the origin.
""",
    ),
    Section(
        key="exits",
        title="What the exit codes mean",
        body="""
0   it worked
1   something failed that is not one of the below
2   the command was wrong, or a value in it was
3   something named on the command line is not in the register
4   the register refused the write, usually because it is already there
""",
    ),
)


def keys() -> list[str]:
    """Every section name, in the order they are meant to be read."""
    return [section.key for section in SECTIONS]


def section(key: str) -> Section:
    """One section by name."""
    for candidate in SECTIONS:
        if candidate.key == key:
            return candidate
    raise ValidationError("no handbook section by that name", key=key, known=keys())


def render(key: str | None = None) -> str:
    """One section, or the whole thing."""
    if key is not None:
        return section(key).render()
    return "\n".join(item.render() for item in SECTIONS)
