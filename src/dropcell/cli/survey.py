"""Commands that read a survey file and say what is in it.

These are the commands somebody runs the afternoon the contractor's file
arrives, before anybody has decided whether to accept the survey. So they all
work off a file rather than the register, they all print rather than write, and
raising the findings is a separate flag that has to be asked for.

The spike pass runs before the sections are cut. A contact spike sitting in the
middle of a good stretch would otherwise split one clean run into two findings
and put a fictitious under criterion reading between them.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import click

from dropcell.cli.context import Context, handled, pass_context
from dropcell.criteria.potential import DEFAULT_PROTECTION_MV
from dropcell.findings.raise_from import from_cis_sections
from dropcell.ingest.cis import import_cis
from dropcell.report.table import Column, Table
from dropcell.stationing import Convention
from dropcell.store.findings import FindingRepository
from dropcell.store.lines import LineRepository
from dropcell.survey.cis import CisSurvey
from dropcell.survey.sections import find_under_criterion, total_under_criterion_m
from dropcell.survey.spikes import find_spikes, without_spikes
from dropcell.units import parse_length_m, parse_potential_mv

SECTION_COLUMNS = (
    Column("from", "From", align="right"),
    Column("to", "To", align="right"),
    Column("length", "Length m", align="right", format=".1f"),
    Column("readings", "Readings", align="right"),
    Column("worst", "Worst mV", align="right", format=".0f"),
    Column("mean", "Mean mV", align="right", format=".0f"),
    Column("short", "Short by mV", align="right", format=".0f"),
    Column("severity", "Severity"),
)

SPIKE_COLUMNS = (
    Column("at", "At", align="right"),
    Column("off", "Off mV", align="right", format=".0f"),
    Column("median", "Local mV", align="right", format=".0f"),
    Column("departure", "Departure mV", align="right", format=".0f"),
)


@click.group("survey")
def survey_group() -> None:
    """Read a survey file and say what is in it."""


@survey_group.command("cis")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--line", "line_code", required=True)
@click.option("--date", "taken_on", required=True, help="Date the survey was walked.")
@click.option("--threshold", default="-850 mV", show_default=True)
@click.option("--gap", default="0 m", show_default=True, help="Bridge gaps up to this.")
@click.option("--minimum", default="0 m", show_default=True, help="Drop sections shorter.")
@click.option("--step", default=None, help="Override the walking interval.")
@click.option("--keep-spikes", is_flag=True, help="Do not drop suspected contact spikes.")
@click.option("--raise-findings", is_flag=True, help="Write the sections to the register.")
@click.option("--by", "actor", default="")
@pass_context
@handled
def analyse_cis(
    context: Context,
    path: Path,
    line_code: str,
    taken_on: str,
    threshold: str,
    gap: str,
    minimum: str,
    step: str | None,
    keep_spikes: bool,
    raise_findings: bool,
    actor: str,
) -> None:
    """Read a close interval file and cut it into sections."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    loaded = import_cis(
        database,
        path.read_text(encoding="utf-8"),
        line_code=line.code,
        taken_on=dt.date.fromisoformat(taken_on),
        now=dt.datetime.combine(context.today, dt.time(12, 0)),
        source=path.name,
        convention=line.convention,
        nominal_interval_m=None if step is None else parse_length_m(step),
    )
    survey = loaded.survey
    spikes = find_spikes(survey)
    if spikes and not keep_spikes:
        survey = without_spikes(survey, spikes)
    sections = find_under_criterion(
        survey,
        threshold_mv=parse_potential_mv(threshold),
        gap_tolerance_m=parse_length_m(gap),
        minimum_length_m=parse_length_m(minimum),
    )
    _print_survey(survey, loaded.quarantined, line.convention)
    if spikes:
        click.echo("")
        click.echo(_spike_table(spikes, line.convention, keep_spikes).render())
    click.echo("")
    click.echo(_section_table(sections, line.convention).render())
    click.echo("")
    click.echo(
        f"{len(sections)} sections, {total_under_criterion_m(sections):.0f} m under criterion"
    )
    if not raise_findings:
        return
    findings = FindingRepository(database)
    made = from_cis_sections(
        sections,
        line_code=line.code,
        raised_on=context.today,
        source=path.name,
        existing_codes=[item.code for item in findings.all()],
    )
    for finding in made:
        findings.raise_finding(finding, actor=actor)
    click.echo(f"{len(made)} findings raised")


def _print_survey(survey: CisSurvey, held: int, convention: Convention) -> None:
    click.echo(f"{survey.line_code} walked {survey.taken_on.isoformat()}")
    click.echo(
        f"{len(survey.points)} steps over {survey.length_m:.0f} m "
        f"at {survey.nominal_interval_m:.2f} m"
    )
    click.echo(f"extent {survey.extent.format(convention)}")
    click.echo(f"interruption caught on {survey.interruption_coverage:.0%} of steps")
    if held:
        click.echo(f"{held} rows could not be read")
    gaps = survey.gaps()
    if gaps:
        click.echo(f"{len(gaps)} stretches were stepped over rather than walked")


def _section_table(sections: list, convention: Convention) -> Table:  # type: ignore[type-arg]
    table = Table(
        columns=SECTION_COLUMNS,
        title="Under criterion",
        empty_note="nothing under criterion",
    )
    for section in sections:
        table.add(
            **{
                "from": section.extent.start.format(convention),
                "to": section.extent.end.format(convention),
            },
            length=section.length_m,
            readings=section.readings,
            worst=section.worst_off_mv,
            mean=section.mean_off_mv,
            short=section.worst_shortfall_mv,
            severity=str(section.severity),
        )
    return table


def _spike_table(spikes: list, convention: Convention, kept: bool) -> Table:  # type: ignore[type-arg]
    title = "Suspected contact spikes, kept" if kept else "Suspected contact spikes, dropped"
    table = Table(columns=SPIKE_COLUMNS, title=title)
    for spike in spikes:
        table.add(
            at=spike.point.station.format(convention),
            off=spike.point.off_mv,
            median=spike.local_median_off_mv,
            departure=spike.departure_mv,
        )
    return table


DEFAULT_THRESHOLD_MV = DEFAULT_PROTECTION_MV
