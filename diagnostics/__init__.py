"""D1-D6 diagnostics. Run on every build; a failure stops downstream work.

Each ``Dn_*.py`` module is runnable (``python -m diagnostics.D1_tire_card``),
writes a machine-readable report to ``diagnostics/out/``, and exits non-zero if
any assertion fails. ``docs/result-evaluation-guide.md`` Part B Gate 1 is what
they collectively enforce: a violation is a bug, not a discovery.
"""
