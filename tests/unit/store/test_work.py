from __future__ import annotations

import datetime as dt

import pytest

from dropcell.errors import ConflictError, NotFoundError
from dropcell.findings.finding import Finding, FindingKind
from dropcell.findings.work import WorkKind, WorkOrder, WorkState
from dropcell.model.line import Line
from dropcell.stationing import Station, StationRange
from dropcell.store.database import Database
from dropcell.store.findings import FindingRepository
from dropcell.store.lines import LineRepository
from dropcell.store.work import WorkOrderRepository

RAISED = dt.date(2025, 3, 14)


@pytest.fixture
def register(database: Database, line: Line) -> Database:
    LineRepository(database).add(line)
    findings = FindingRepository(database)
    for code in ("F-2025-001", "F-2025-002", "F-2025-003"):
        findings.raise_finding(
            Finding(
                code=code,
                line_code="AL-2",
                kind=FindingKind.UNDER_CRITERION,
                raised_on=RAISED,
                extent=StationRange(Station(1200.0), Station(1260.0)),
                summary="under criterion",
            )
        )
    return database


def order(**overrides: object) -> WorkOrder:
    kwargs: dict[str, object] = {
        "code": "WO-2025-004",
        "line_code": "AL-2",
        "kind": WorkKind.EXCAVATION,
        "raised_on": RAISED,
        "finding_codes": ("F-2025-001",),
        "summary": "dig and recoat",
    }
    kwargs.update(overrides)
    return WorkOrder(**kwargs)  # type: ignore[arg-type]


def test_an_order_survives_a_round_trip(register: Database) -> None:
    orders = WorkOrderRepository(register)
    original = order(
        finding_codes=("F-2025-001", "F-2025-002"),
        planned_for=dt.date(2025, 6, 1),
        contractor="Bright Excavations",
        estimate=4200.0,
    )
    orders.add(original)
    assert orders.get("WO-2025-004") == original


def test_an_order_against_a_finding_that_is_not_there_is_refused(
    register: Database,
) -> None:
    with pytest.raises(ConflictError):
        WorkOrderRepository(register).add(order(finding_codes=("F-2025-999",)))


def test_an_order_with_no_findings_is_allowed(register: Database) -> None:
    orders = WorkOrderRepository(register)
    orders.add(order(finding_codes=(), kind=WorkKind.SURVEY, summary="walk the line"))
    assert orders.get("WO-2025-004").findings == 0


def test_the_findings_of_an_order_can_be_replaced(register: Database) -> None:
    import dataclasses

    orders = WorkOrderRepository(register)
    orders.add(order(finding_codes=("F-2025-001", "F-2025-002")))
    amended = dataclasses.replace(orders.get("WO-2025-004"), finding_codes=("F-2025-003",))
    orders.replace(amended)
    assert orders.get("WO-2025-004").finding_codes == ("F-2025-003",)


def test_replacing_an_order_that_is_not_there_is_refused(register: Database) -> None:
    with pytest.raises(NotFoundError):
        WorkOrderRepository(register).replace(order())


def test_an_order_can_be_found_from_a_finding(register: Database) -> None:
    orders = WorkOrderRepository(register)
    orders.add(order(finding_codes=("F-2025-001", "F-2025-002")))
    assert [item.code for item in orders.against("F-2025-002")] == ["WO-2025-004"]
    assert orders.against("F-2025-003") == []


def test_orders_on_a_line_can_be_narrowed_to_the_live_ones(
    register: Database,
) -> None:
    orders = WorkOrderRepository(register)
    orders.add(order())
    orders.add(order(code="WO-2025-005", finding_codes=("F-2025-002",)))
    orders.move("WO-2025-005", WorkState.CANCELLED, on=RAISED)
    assert len(orders.for_line("AL-2")) == 2
    assert [item.code for item in orders.for_line("AL-2", open_only=True)] == ["WO-2025-004"]


def test_moving_an_order_through_to_done_stamps_the_date(register: Database) -> None:
    orders = WorkOrderRepository(register)
    orders.add(order())
    orders.move("WO-2025-004", WorkState.ISSUED, on=RAISED)
    orders.move("WO-2025-004", WorkState.IN_PROGRESS, on=RAISED)
    done = orders.move("WO-2025-004", WorkState.DONE, on=dt.date(2025, 6, 4))
    assert done.state is WorkState.DONE
    assert done.completed_on == dt.date(2025, 6, 4)


def test_a_transition_the_state_machine_forbids_is_refused(
    register: Database,
) -> None:
    orders = WorkOrderRepository(register)
    orders.add(order())
    with pytest.raises(ConflictError) as caught:
        orders.move("WO-2025-004", WorkState.DONE, on=RAISED)
    assert caught.value.detail["wanted"] == "done"


def test_a_finished_order_cannot_be_moved_again(register: Database) -> None:
    orders = WorkOrderRepository(register)
    orders.add(order())
    orders.move("WO-2025-004", WorkState.ISSUED, on=RAISED)
    orders.move("WO-2025-004", WorkState.DONE, on=RAISED)
    with pytest.raises(ConflictError):
        orders.move("WO-2025-004", WorkState.DRAFT, on=RAISED)


def test_completing_an_order_does_not_close_its_findings(register: Database) -> None:
    orders = WorkOrderRepository(register)
    orders.add(order())
    orders.move("WO-2025-004", WorkState.ISSUED, on=RAISED)
    orders.move("WO-2025-004", WorkState.DONE, on=RAISED)
    assert FindingRepository(register).get("F-2025-001").is_open


def test_deleting_a_finding_unlinks_it_from_its_orders(register: Database) -> None:
    orders = WorkOrderRepository(register)
    orders.add(order(finding_codes=("F-2025-001", "F-2025-002")))
    FindingRepository(register).delete("F-2025-001")
    assert orders.get("WO-2025-004").finding_codes == ("F-2025-002",)


def test_deleting_a_line_takes_its_orders_with_it(register: Database) -> None:
    orders = WorkOrderRepository(register)
    orders.add(order())
    LineRepository(register).delete("AL-2")
    assert orders.count() == 0
