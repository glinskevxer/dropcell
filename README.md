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
```

## Layout

```
src/dropcell/     the package
tests/            unit and integration tests
```
