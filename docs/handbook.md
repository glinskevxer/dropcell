# dropcell handbook

## What this is for

A cathodic protection programme produces a lot of numbers and very few
decisions. This tool holds the numbers and makes the decisions explicit.

## The order of a year

1. `dropcell init` once, to make the register.
2. `dropcell line add` and `dropcell segment add` to describe the pipe.
3. `dropcell post add` for every test post, with the leads it carries.
4. `dropcell rectifier add-bed` then `dropcell rectifier add` for the plant.
5. `dropcell import annual` when the survey file arrives.
6. `dropcell rectifier check` six times a year, or `dropcell import rectifier`.
7. `dropcell report protection` and `dropcell report compliance` monthly.
8. `dropcell survey cis` when a close interval survey lands.
9. `dropcell finding` to work the exceptions through.

## Reading the reports

`report protection` splits the posts three ways and the third group is the one
to read first. A post that could not be judged is missing field work, not a
passing post and not a failing one.

`report compliance` counts asset and rule pairs, not visits. A rule has two
halves, a count per calendar year and a maximum interval, and a programme can
satisfy either one on its own while failing the other.

`report coverage` is over line length. A hundred percent protection over one
percent of the line is a normal state of affairs on a line with posts a mile
apart, and it is what this report exists to show.

`plan trend` fits a straight line through each post's history. It will not fit
fewer than three readings and it will not extrapolate past the horizon.

The `report` group answers questions somebody has today. The `plan` group is
read once a quarter by somebody deciding where next year's money goes.

## Units

Every option that takes a measurement takes it with a unit. A bare number in a
potential column is millivolts. A bare number in a rectifier output column is
volts. Those two defaults disagree on purpose.

## Stationing

A line is surveyed in feet or in metres and every station is printed back in
whichever it was. Inside the register everything is metres from the line origin.
