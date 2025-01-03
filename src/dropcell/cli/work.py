"""Commands for work orders.

An order is raised against findings that already exist, so the codes are given
rather than looked up, and a code that is not in the register stops the command.
That is deliberate: an order against a finding nobody raised is an order nobody
will find again.

Completing an order does not clear its findings, and the command says so every
time. The temptation to make it do both is strong and it is the wrong trade,
because what closes a finding is a reading, not a crew going home.
"""

from __future__ import annotations

import datetime as dt

import click

from dropcell.cli.context import Context, handled, pass_context
from dropcell.findings.raise_from import next_sequence
from dropcell.findings.work import WorkKind, WorkOrder, WorkState
from dropcell.report.table import Column, Table
from dropcell.store.findings import FindingRepository
from dropcell.store.lines import LineRepository
from dropcell.store.work import WorkOrderRepository

WORK_COLUMNS = (
    Column("code", "Order"),
    Column("kind", "Kind", width=18),
    Column("state", "State"),
    Column("raised", "Raised"),
    Column("planned", "Planned"),
    Column("findings", "Findings", align="right"),
    Column("estimate", "Estimate", align="right", format=".0f"),
    Column("actual", "Actual", align="right", format=".0f"),
    Column("summary", "Summary", width=34),
)


def _next_code(orders: WorkOrderRepository, year: int) -> str:
    existing = [item.code.replace("WO-", "F-") for item in orders.all()]
    return f"WO-{year:04d}-{next_sequence(existing, year):03d}"


@click.group("work")
def work_group() -> None:
    """Raise and track work orders."""


@work_group.command("raise")
@click.option("--line", "line_code", required=True)
@click.option("--kind", type=click.Choice([str(item) for item in WorkKind]), required=True)
@click.option("--summary", required=True)
@click.option("--finding", "finding_codes", multiple=True, help="Give once per finding.")
@click.option("--planned", default=None, help="Date the job is booked for.")
@click.option("--contractor", default="")
@click.option("--estimate", type=float, default=None)
@pass_context
@handled
def raise_order(
    context: Context,
    line_code: str,
    kind: str,
    summary: str,
    finding_codes: tuple[str, ...],
    planned: str | None,
    contractor: str,
    estimate: float | None,
) -> None:
    """Raise a work order against nothing, one finding, or several."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    findings = FindingRepository(database)
    for code in finding_codes:
        findings.get(code)
    orders = WorkOrderRepository(database)
    order = WorkOrder(
        code=_next_code(orders, context.today.year),
        line_code=line.code,
        kind=WorkKind(kind),
        raised_on=context.today,
        finding_codes=finding_codes,
        summary=summary,
        planned_for=dt.date.fromisoformat(planned) if planned else None,
        contractor=contractor,
        estimate=estimate,
    )
    orders.add(order)
    click.echo(f"{order.code} raised against {order.findings} findings")
    if order.kind.breaks_ground:
        click.echo("  this job breaks ground, so it needs a permit and a service search")


@work_group.command("issue")
@click.argument("code")
@pass_context
@handled
def issue_order(context: Context, code: str) -> None:
    """Issue a draft order to a contractor."""
    moved = WorkOrderRepository(context.database()).move(
        code, WorkState.ISSUED, on=context.today
    )
    click.echo(f"{moved.code} issued")


@work_group.command("start")
@click.argument("code")
@pass_context
@handled
def start_order(context: Context, code: str) -> None:
    """Mark an order as being worked on."""
    moved = WorkOrderRepository(context.database()).move(
        code, WorkState.IN_PROGRESS, on=context.today
    )
    click.echo(f"{moved.code} in progress")


@work_group.command("done")
@click.argument("code")
@click.option("--cost", "actual", type=float, default=None, help="What it actually cost.")
@pass_context
@handled
def finish_order(context: Context, code: str, actual: float | None) -> None:
    """Mark an order finished. This does not clear its findings."""
    import dataclasses

    orders = WorkOrderRepository(context.database())
    moved = orders.move(code, WorkState.DONE, on=context.today)
    if actual is not None:
        moved = orders.replace(dataclasses.replace(moved, actual=actual))
    click.echo(f"{moved.code} finished on {context.today.isoformat()}")
    if moved.variance is not None:
        click.echo(f"  {moved.variance:+.0f} against an estimate of {moved.estimate:.0f}")
    if moved.kind.needs_reread and moved.findings:
        codes = ", ".join(moved.finding_codes)
        click.echo(f"  {codes} stay open until a reading proves the work took")


@work_group.command("cancel")
@click.argument("code")
@pass_context
@handled
def cancel_order(context: Context, code: str) -> None:
    """Cancel an order."""
    moved = WorkOrderRepository(context.database()).move(
        code, WorkState.CANCELLED, on=context.today
    )
    click.echo(f"{moved.code} cancelled")


@work_group.command("list")
@click.option("--line", "line_code", required=True)
@click.option("--open", "open_only", is_flag=True, help="Only the live ones.")
@pass_context
@handled
def list_orders(context: Context, line_code: str, open_only: bool) -> None:
    """List the work orders on a line."""
    database = context.database()
    line = LineRepository(database).get(line_code)
    orders = WorkOrderRepository(database).for_line(line.code, open_only=open_only)
    table = Table(columns=WORK_COLUMNS, empty_note="no work orders on this line")
    for order in orders:
        table.add(
            code=order.code,
            kind=str(order.kind),
            state=str(order.state),
            raised=order.raised_on.isoformat(),
            planned=order.planned_for.isoformat() if order.planned_for else "",
            findings=order.findings,
            estimate=order.estimate,
            actual=order.actual,
            summary=order.summary,
        )
    click.echo(table.render())


@work_group.command("show")
@click.argument("code")
@pass_context
@handled
def show_order(context: Context, code: str) -> None:
    """Show one order and the findings on it."""
    database = context.database()
    orders = WorkOrderRepository(database)
    findings = FindingRepository(database)
    order = orders.get(code)
    click.echo(f"{order.code}  {order.kind}  {order.state}")
    click.echo(f"line       {order.line_code}")
    click.echo(f"raised     {order.raised_on.isoformat()}")
    click.echo(
        f"planned    {order.planned_for.isoformat() if order.planned_for else 'not yet'}"
    )
    if order.contractor:
        click.echo(f"contractor {order.contractor}")
    if order.estimate is not None:
        click.echo(f"estimate   {order.estimate:.0f}")
    if order.actual is not None:
        click.echo(f"actual     {order.actual:.0f}")
    click.echo(f"summary    {order.summary}")
    click.echo("")
    if not order.finding_codes:
        click.echo("no findings on this order")
        return
    for finding_code in order.finding_codes:
        finding = findings.get(finding_code)
        click.echo(f"  {finding.code}  {finding.state:<10}  {finding.summary}")
