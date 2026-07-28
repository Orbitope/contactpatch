"""Shared plumbing for the D1-D6 diagnostics: check records, reports, exit codes."""

from __future__ import annotations

import json
import math
import textwrap
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

OUT_DIR = Path(__file__).resolve().parent / "out"

_GREEN, _RED, _YELLOW, _DIM, _BOLD, _RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
)


@dataclass
class Check:
    """One assertion, with enough context to act on a failure.

    ``severity``:
        ``"gate"``  — a Gate 1 falsification check. Failure stops the build.
        ``"note"``  — recorded and printed, never fails. Used where the model
                      is *correct* but a reference document is not, or where a
                      number is worth watching but is not a pass/fail claim.

    ``group`` is a plain-English question the check helps answer. It exists
    because a wall of 60 assertions named ``peak_mu@3929N`` is unreadable, and
    ``docs/result-evaluation-guide.md`` opens by promising that "is the physics
    right?" is checkable *without* vehicle-dynamics expertise.
    """

    name: str
    passed: bool
    detail: str
    severity: str = "gate"
    value: Any = None
    expected: Any = None
    group: str = "Checks"

    @property
    def blocking(self) -> bool:
        return self.severity == "gate" and not self.passed


@dataclass
class Report:
    diagnostic: str
    title: str
    subtitle: str = ""
    checks: list[Check] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    #: Plain-English statements of what the run *found*, for a reader who does
    #: not know what a slip angle is. Written by the diagnostic, printed first.
    findings: list[str] = field(default_factory=list)
    _group: str = "Checks"

    def section(self, group: str) -> None:
        """Set the plain-English question that following checks answer."""
        self._group = group

    def add(self, name: str, passed: bool, detail: str, **kw) -> Check:
        kw.setdefault("group", self._group)
        c = Check(name=name, passed=bool(passed), detail=detail, **kw)
        self.checks.append(c)
        return c

    def find(self, text: str) -> None:
        """Record a plain-English finding."""
        self.findings.append(text)

    def note(self, name: str, detail: str, **kw) -> Check:
        return self.add(name, True, detail, severity="note", **kw)

    def close(self, value, target, tol, name: str, unit: str = "", rel: bool = False):
        """Assert ``value`` is within ``tol`` of ``target``; record either way."""
        err = abs(value - target)
        if rel:
            err = err / abs(target) if target else math.inf
        ok = err <= tol
        unit_s = f" {unit}" if unit else ""
        kind = "rel" if rel else "abs"
        self.add(
            name,
            ok,
            f"{value:.4g}{unit_s} vs {target:.4g}{unit_s} "
            f"({kind} err {err:.3g}, tol {tol:.3g})",
            value=float(value),
            expected=float(target),
        )
        return ok

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if c.blocking]

    @property
    def ok(self) -> bool:
        return not self.failures

    def write(self, out_dir: Path = OUT_DIR) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{self.diagnostic}_report.json"
        path.write_text(
            json.dumps(
                {
                    "diagnostic": self.diagnostic,
                    "title": self.title,
                    "subtitle": self.subtitle,
                    "passed": self.ok,
                    "n_checks": len(self.checks),
                    "n_failed": len(self.failures),
                    "findings": self.findings,
                    "checks": [asdict(c) for c in self.checks],
                    "data": self.data,
                },
                indent=2,
                default=float,
            )
            + "\n"
        )
        return path

    def write_markdown(self, figures=None, out_dir: Path = OUT_DIR,
                       command: str = "") -> Path:
        """Write the consolidated human-readable write-up for this diagnostic.

        One file per diagnostic, holding the plain-English summary, every figure
        it produced with a caption, the check groups, the technical notes and the
        headline numbers. **Generated, never hand-written**, so it cannot drift
        from the code the way a manually maintained document does. This is the
        raw material an episode draft is written from.

        ``figures`` is a list of ``(label, path, caption)``.
        """
        out_dir.mkdir(parents=True, exist_ok=True)
        gates = [c for c in self.checks if c.severity == "gate"]
        notes = [c for c in self.checks if c.severity == "note"]
        groups: dict[str, list[Check]] = {}
        for c in gates:
            groups.setdefault(c.group, []).append(c)

        L: list[str] = [
            f"# {self.diagnostic} — {self.title}",
            "",
            "*Generated by "
            f"`{command or f'python -m diagnostics.{self.diagnostic}'}`. "
            "Do not edit — re-run it.*",
            "",
        ]
        if self.subtitle:
            L += [f"**What this checks.** {self.subtitle}", ""]
        status = ("**PASSED**" if self.ok
                  else f"**FAILED — {len(self.failures)} of {len(gates)}**")
        L += [f"{status} · {sum(c.passed for c in gates)}/{len(gates)} checks · "
              f"{len(notes)} technical notes", "", "---", ""]

        if self.findings:
            L += ["## What this found", ""]
            L += [f"- {f}" for f in self.findings] + [""]

        if figures:
            L += ["## Figures", ""]
            for label, path, caption in figures:
                name = Path(path).name
                L += [f"### {label}", "", f"![{label}]({name})", "",
                      f"{caption}", "", f"`{name}`", ""]

        L += ["## What was checked", "",
              "| Question | Checks | |", "|---|---|---|"]
        for group, items in groups.items():
            bad = sum(not c.passed for c in items)
            L.append(f"| {group} | {sum(c.passed for c in items)}/{len(items)} | "
                     f"{'ok' if not bad else f'**{bad} FAILED**'} |")
        L.append("")

        if self.failures:
            L += ["## Failures", ""]
            for c in self.failures:
                L += [f"### `{c.name}`", "", c.detail, ""]

        if notes:
            L += ["## Technical notes", "",
                  "*Recorded, never pass/fail. These are where the model is "
                  "correct but a reference is not, or where a number is worth "
                  "watching.*", ""]
            for c in notes:
                L += [f"### {c.name}", "", c.detail, ""]

        if self.data:
            L += ["## Key numbers", "", "| | |", "|---|---|"]
            for k, v in self.data.items():
                if isinstance(v, (int, float, str, bool)):
                    L.append(f"| `{k}` | {v} |")
            L += ["", f"Full data, including every individual assertion, in "
                  f"`{self.diagnostic}_report.json`.", ""]

        path = out_dir / f"{self.diagnostic}.md"
        path.write_text("\n".join(L))
        return path

    def print_summary(self, verbose: bool = False) -> None:
        """Human-readable summary.

        Default output answers three questions in order: what was checked, what
        was found, and did it pass. ``verbose`` adds every individual assertion
        and every technical note — that detail always lands in the JSON report
        regardless, so the console does not have to carry it.
        """
        gates = [c for c in self.checks if c.severity == "gate"]
        notes = [c for c in self.checks if c.severity == "note"]

        print(f"\n{_BOLD}{self.diagnostic} — {self.title}{_RESET}")
        if self.subtitle:
            print(f"{_DIM}{_wrap(self.subtitle, indent=0)}{_RESET}")

        # --- what was checked, grouped by the question it answers ----------
        print()
        groups: dict[str, list[Check]] = {}
        for c in gates:
            groups.setdefault(c.group, []).append(c)
        width = max((len(g) for g in groups), default=0)
        for group, items in groups.items():
            n_ok = sum(c.passed for c in items)
            bad = len(items) - n_ok
            mark = f"{_GREEN}ok{_RESET}" if not bad else f"{_RED}{bad} FAILED{_RESET}"
            print(f"  {group:<{width}}  {n_ok:>2}/{len(items):<2}  {mark}")

        # --- what it found -------------------------------------------------
        if self.findings:
            print(f"\n{_BOLD}  What this found{_RESET}")
            for f in self.findings:
                print(_wrap(f, bullet="  · ", indent=4))

        # --- failures always shown in full ---------------------------------
        for c in self.failures:
            print(f"\n  [{_RED}FAIL{_RESET}] {c.name}")
            print(_wrap(c.detail, indent=9))

        if verbose:
            print(f"\n{_BOLD}  All checks{_RESET}")
            for group, items in groups.items():
                print(f"\n  {group}")
                for c in items:
                    mark = f"{_GREEN}pass{_RESET}" if c.passed else f"{_RED}FAIL{_RESET}"
                    print(f"    [{mark}] {c.name}: {c.detail}")
            print(f"\n{_BOLD}  Technical notes{_RESET}")
            for c in notes:
                print(f"\n  {_YELLOW}{c.name}{_RESET}")
                print(_wrap(c.detail, indent=4))

        n_pass = sum(c.passed for c in gates)
        print()
        if self.ok:
            print(f"{_GREEN}{self.diagnostic} PASSED{_RESET} — {n_pass}/{len(gates)} "
                  f"checks. {len(notes)} technical notes recorded.")
            if not verbose:
                print(f"{_DIM}Run with -v for every check and every note.{_RESET}")
        else:
            print(f"{_RED}{self.diagnostic} FAILED{_RESET} "
                  f"— {len(self.failures)} of {len(gates)} checks failed.")
            print(f"{_DIM}Gate 1 failure: stop downstream work. "
                  f"See docs/result-evaluation-guide.md Part C.{_RESET}")


def _wrap(text: str, width: int = 88, indent: int = 4, bullet: str = "") -> str:
    """Wrap prose to a readable column, with a hanging indent."""
    lead = bullet or " " * indent
    body = textwrap.wrap(text, width=width - indent)
    if not body:
        return ""
    out = [lead + body[0]]
    out += [" " * len(lead) + line for line in body[1:]]
    return "\n".join(out)
