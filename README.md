# dropcell

Cathodic protection monitoring and compliance for buried steel pipelines.

A technician walks the line with a copper/copper-sulfate half cell, drops it in
the soil over the pipe at every test post, and reads the potential between the
steel and the ground. That reading is the whole of the evidence that the pipe is
not corroding. `dropcell` is the register those readings land in, and the engine
that decides whether the line is protected, where it is not, and what is overdue.

It is a command line tool over a SQLite file. No server, no web UI.

## Running it

```
pip install -e ".[dev]"
dropcell --help
dropcell handbook
```

`dropcell handbook` is the documentation. It ships inside the package, so it is
there on a laptop in a depot with no checkout of this repository.

## What it holds

Lines, segments, test posts and their readings. Rectifiers, groundbeds and their
check sheets. Casings, foreign crossings, bonds and isolating joints, with the
tests taken on them. Coupons, soil soundings, close interval and gradient
surveys. Findings, work orders and free text notes.

## What it works out

Whether a point meets a protection criterion, and which one. Where a close
interval trace falls under criterion and for how far. How a gradient survey's
defects rank for excavation. How much of a groundbed is left. Whether a
monitoring obligation has been met, counting the calendar year rule and the
maximum interval rule separately, because a programme can satisfy either one
while failing the other.

## What it will not do

It will not decide that a post which nobody read is protected. It will not
average a reading taken through a bad contact into a length of pipe. It will not
report a rate without saying what it is a rate of. Most of the code in here is
about those three.

## Layout

```
src/dropcell/     the package
  model/          the records
  criteria/       whether a point is protected
  survey/         close interval, gradient, depolarisation
  interference/   casings, crossings, bonds, isolating joints
  analysis/       what the records add up to
  schedule/       what is due and what is late
  ingest/         getting vendor files in
  store/          SQLite, migrations, repositories
  report/         turning it into something a person reads
  cli/            the command line
tests/            unit and integration tests
docs/             the handbook, also available as a command
```

## Development

```
make check        everything the pipeline runs
make cover        the same with a coverage gate at 90 percent
```

Python 3.12, ruff, mypy in strict mode, pytest. Every dependency is pinned.
