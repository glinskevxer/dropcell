# Changelog

## 1.0.0

The first version whose interfaces are meant to be relied on.

What that promise covers is the list in `dropcell.__all__`, the exit codes, the
transfer document format, and the shape of the JSON the reports emit. Anything
else in the package can change.

Added since the register first held a reading: close interval and gradient
surveys, depolarisation, coupons and AC criteria, casings, foreign crossings,
bonds and isolating joints, groundbed life, soil soundings, work orders, free
text notes, a settings file with an operator's own thresholds, a transfer
document for handing a line over, and a handbook that ships in the package.

Fifteen schema migrations, applied in order and checksummed, so a register built
against the first of them opens against the last.
