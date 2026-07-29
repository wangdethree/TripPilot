"""Validate the offline Agent regression dataset and emit a release report."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REQUIRED_COUNTS = {
    "normal_planning": 12,
    "requirements": 10,
    "constraints": 12,
    "tool_failures": 10,
    "modification": 8,
    "security": 8,
}


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    dataset_version: str
    total: int
    passed: int
    failed: int
    hard_gate_passed: bool
    category_counts: dict[str, int]
    failures: tuple[str, ...]


def load_scenarios(path: Path) -> tuple[dict[str, Any], ...]:
    scenarios: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"评测数据第 {line_number} 行不是合法 JSON") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"评测数据第 {line_number} 行必须是对象")
        scenarios.append(raw)
    return tuple(scenarios)


def run_contract_evaluation(
    scenarios: tuple[dict[str, Any], ...],
    *,
    dataset_version: str,
) -> EvaluationReport:
    failures: list[str] = []
    ids: set[str] = set()
    counts: Counter[str] = Counter()
    required_fields = {
        "id",
        "category",
        "input",
        "expected_status",
        "expected_tools",
        "assertions",
    }
    for index, scenario in enumerate(scenarios, start=1):
        missing = required_fields - scenario.keys()
        scenario_id = str(scenario.get("id", f"line-{index}"))
        if missing:
            failures.append(f"{scenario_id}: missing {sorted(missing)}")
            continue
        if scenario_id in ids:
            failures.append(f"{scenario_id}: duplicate id")
        ids.add(scenario_id)
        category = str(scenario["category"])
        counts[category] += 1
        if category not in REQUIRED_COUNTS:
            failures.append(f"{scenario_id}: unknown category {category}")
        if not isinstance(scenario["input"], list) or not scenario["input"]:
            failures.append(f"{scenario_id}: input must be a non-empty dialogue list")
        if not isinstance(scenario["expected_tools"], list):
            failures.append(f"{scenario_id}: expected_tools must be a list")
        if not isinstance(scenario["assertions"], list) or not scenario["assertions"]:
            failures.append(f"{scenario_id}: assertions must be non-empty")
    for category, minimum in REQUIRED_COUNTS.items():
        actual = counts[category]
        if actual < minimum:
            failures.append(f"{category}: expected at least {minimum}, got {actual}")
    return EvaluationReport(
        dataset_version=dataset_version,
        total=len(scenarios),
        passed=len(scenarios) - len({failure.split(":", maxsplit=1)[0] for failure in failures}),
        failed=len(failures),
        hard_gate_passed=not failures,
        category_counts=dict(sorted(counts.items())),
        failures=tuple(failures),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="TripPilot offline evaluation")
    parser.add_argument(
        "dataset",
        nargs="?",
        type=Path,
        default=Path("evals/scenarios-v1.jsonl"),
    )
    parser.add_argument("--dataset-version", default="v1.0.0")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_contract_evaluation(
        load_scenarios(args.dataset),
        dataset_version=args.dataset_version,
    )
    rendered = json.dumps(asdict(report), ensure_ascii=False, indent=2)
    if args.output is not None:
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    print(rendered)
    return 0 if report.hard_gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
