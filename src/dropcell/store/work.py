"""Reading and writing work orders and what they are against.

The link between orders and findings is a table of its own because it is many
to many in both directions, and because the question asked most often is the
awkward one: given this finding, is anybody doing anything about it. That reads
off the link table with an index on the finding, which is why the index is there.

Changing which findings an order covers replaces the whole set rather than
adding to it. A crew that turns up and finds two of the three defects amends the
order, and an interface that only appends leaves the third one attached to a job
that did not touch it.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from dropcell.errors import ConflictError, NotFoundError
from dropcell.findings.work import WorkKind, WorkOrder, WorkState
from dropcell.model.ids import normalise_code
from dropcell.store.base import Repository

WORK_COLUMNS = (
    "code, line_code, kind, raised_on, summary, state, planned_for, completed_on, "
    "contractor, estimate, actual, notes"
)


def _date(value: object) -> dt.date | None:
    return None if value is None else dt.date.fromisoformat(str(value))


class WorkOrderRepository(Repository[WorkOrder]):
    """Every job in the register."""

    table = "work_order"
    columns = WORK_COLUMNS
    noun = "work order"
    order_by = "line_code, raised_on, code"

    def to_record(self, row: sqlite3.Row) -> WorkOrder:
        """Rebuild an order from a register row, then attach its findings."""
        code = str(row["code"])
        return WorkOrder(
            code=code,
            line_code=str(row["line_code"]),
            kind=WorkKind(row["kind"]),
            raised_on=dt.date.fromisoformat(str(row["raised_on"])),
            finding_codes=tuple(self.finding_codes(code)),
            summary=str(row["summary"]),
            state=WorkState(row["state"]),
            planned_for=_date(row["planned_for"]),
            completed_on=_date(row["completed_on"]),
            contractor=str(row["contractor"]),
            estimate=None if row["estimate"] is None else float(row["estimate"]),
            actual=None if row["actual"] is None else float(row["actual"]),
            notes=str(row["notes"]),
        )

    def finding_codes(self, code: str) -> list[str]:
        """The findings one order is against."""
        rows = self.database.query(
            "SELECT finding_code FROM work_order_finding WHERE work_order_code = ?"
            " ORDER BY finding_code",
            (normalise_code(code, kind="work order code"),),
        )
        return [str(row["finding_code"]) for row in rows]

    def add(self, order: WorkOrder) -> WorkOrder:
        """Insert an order and link it to its findings."""
        with self.database.transaction():
            self.database.execute(
                f"INSERT INTO work_order ({WORK_COLUMNS})"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    order.code,
                    order.line_code,
                    str(order.kind),
                    order.raised_on.isoformat(),
                    order.summary,
                    str(order.state),
                    None if order.planned_for is None else order.planned_for.isoformat(),
                    None if order.completed_on is None else order.completed_on.isoformat(),
                    order.contractor,
                    order.estimate,
                    order.actual,
                    order.notes,
                ),
            )
            self._link(order.code, order.finding_codes)
        return order

    def replace(self, order: WorkOrder) -> WorkOrder:
        """Overwrite an order and its links."""
        with self.database.transaction():
            cursor = self.database.execute(
                "UPDATE work_order SET line_code = ?, kind = ?, raised_on = ?,"
                " summary = ?, state = ?, planned_for = ?, completed_on = ?,"
                " contractor = ?, estimate = ?, actual = ?, notes = ? WHERE code = ?",
                (
                    order.line_code,
                    str(order.kind),
                    order.raised_on.isoformat(),
                    order.summary,
                    str(order.state),
                    None if order.planned_for is None else order.planned_for.isoformat(),
                    None if order.completed_on is None else order.completed_on.isoformat(),
                    order.contractor,
                    order.estimate,
                    order.actual,
                    order.notes,
                    order.code,
                ),
            )
            if cursor.rowcount == 0:
                raise NotFoundError("no work order with that code", code=order.code)
            self.database.execute(
                "DELETE FROM work_order_finding WHERE work_order_code = ?", (order.code,)
            )
            self._link(order.code, order.finding_codes)
        return order

    def move(self, code: str, state: WorkState, *, on: dt.date) -> WorkOrder:
        """Move an order to another state, refusing a transition that is not allowed."""
        import dataclasses

        current = self.get(code)
        if not current.can_move_to(state):
            raise ConflictError(
                "a work order cannot go from one of those states to the other",
                code=current.code,
                state=str(current.state),
                wanted=str(state),
            )
        moved = dataclasses.replace(
            current,
            state=state,
            completed_on=on if state is WorkState.DONE else None,
        )
        return self.replace(moved)

    def for_line(self, line_code: str, *, open_only: bool = False) -> list[WorkOrder]:
        """Every order on one line, oldest first."""
        sql = f"SELECT {WORK_COLUMNS} FROM work_order WHERE line_code = ?"
        params: list[object] = [normalise_code(line_code, kind="line code")]
        if open_only:
            sql += " AND state NOT IN ('done', 'cancelled')"
        sql += " ORDER BY raised_on, code"
        return [self.to_record(row) for row in self.database.query(sql, params)]

    def against(self, finding_code: str) -> list[WorkOrder]:
        """Every order that covers one finding."""
        rows = self.database.query(
            "SELECT work_order_code FROM work_order_finding WHERE finding_code = ?"
            " ORDER BY work_order_code",
            (normalise_code(finding_code, kind="finding code"),),
        )
        return [self.get(str(row["work_order_code"])) for row in rows]

    def _link(self, code: str, finding_codes: tuple[str, ...]) -> None:
        if not finding_codes:
            return
        self.database.executemany(
            "INSERT INTO work_order_finding (work_order_code, finding_code) VALUES (?, ?)",
            [(code, finding) for finding in finding_codes],
        )
