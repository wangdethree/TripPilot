from pathlib import Path

from trippilot.evaluation.runner import load_scenarios, run_contract_evaluation


def test_v1_dataset_meets_release_contract() -> None:
    scenarios = load_scenarios(Path("evals/scenarios-v1.jsonl"))

    report = run_contract_evaluation(scenarios, dataset_version="v1.0.0")

    assert report.total == 60
    assert report.failed == 0
    assert report.hard_gate_passed is True
    assert report.category_counts["normal_planning"] == 12
    assert report.category_counts["security"] == 8
