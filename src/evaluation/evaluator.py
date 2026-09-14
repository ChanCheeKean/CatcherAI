from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from domain.case import DecisionRecord
from domain.events import Actor, ActorKind, EventDraft, EventEnvelope
from observability.emitter import EventEmitter


class CheckResult(BaseModel):
    name: str
    passed: bool
    actual: Any = None
    expected: Any = None
    detail: str = ""


class EvalResult(BaseModel):
    case_id: str
    passed: bool
    deterministic: list[CheckResult] = Field(default_factory=list)
    capabilities: list[CheckResult] = Field(default_factory=list)
    trajectory_complete: bool


class GroundTruthEvaluator:
    """Privileged harness component; the runtime has no reference to this path or class."""

    def __init__(self, evaluator_root: Path) -> None:
        self.evaluator_root = evaluator_root.resolve()

    def evaluate(
        self,
        decision: DecisionRecord,
        events: list[EventEnvelope],
        emitter: EventEmitter,
    ) -> EvalResult:
        truth = self._load_truth(decision.case_id)
        record = decision.model_dump(mode="json")
        deterministic = self._expected_subset_checks(record, truth.get("expected", {}))
        deterministic.extend(
            self._evaluate_check(record, check) for check in truth["deterministic_checks"]
        )
        deterministic.extend(self._requirement_checks(record, truth, events))
        capabilities = self._evaluate_capabilities(truth, events)
        trajectory = self._trajectory_complete(events)
        result = EvalResult(
            case_id=decision.case_id,
            passed=(
                all(check.passed for check in deterministic)
                and all(check.passed for check in capabilities)
                and trajectory
            ),
            deterministic=deterministic,
            capabilities=capabilities,
            trajectory_complete=trajectory,
        )
        emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.EVALUATOR, name="ground_truth_evaluator"),
                type="eval_scored",
                summary=f"Evaluation {'passed' if result.passed else 'failed'}",
                payload=result.model_dump(mode="json"),
                refs=[decision.case_id],
            )
        )
        return result

    def evaluate_queue(
        self, ranking: list[dict[str, Any]], events: list[EventEnvelope], emitter: EventEmitter
    ) -> EvalResult:
        """Q01: rank agreement with the generator's deadline-ranked backlog."""

        truth = json.loads((self.evaluator_root / "Q01_queue.json").read_text(encoding="utf-8"))
        ours = {row["case_id"]: row for row in ranking}
        expected_top = [row["case_id"] for row in truth["top_15"]]
        top_n = len(expected_top)
        overlap = len(set(expected_top) & {row["case_id"] for row in ranking[:top_n]})
        tau = _kendall_tau([ours[case_id]["rank"] for case_id in expected_top if case_id in ours])
        deadline_matches = [
            ours.get(row["case_id"], {}).get("next_deadline") == row["next_deadline"]
            for row in truth["all_open"]
        ]
        label_differences = [
            {
                "case_id": row["case_id"],
                "expected": row["next_clock"],
                "actual": ours[row["case_id"]]["next_clock"],
            }
            for row, matched in zip(truth["all_open"], deadline_matches, strict=True)
            if matched
            and row["case_id"] in ours
            and ours[row["case_id"]]["next_clock"] != row["next_clock"]
        ]
        mismatches = [
            {
                "case_id": row["case_id"],
                "expected": [row["next_clock"], row["next_deadline"]],
                "actual": [
                    ours.get(row["case_id"], {}).get("next_clock"),
                    ours.get(row["case_id"], {}).get("next_deadline"),
                ],
            }
            for row, matched in zip(truth["all_open"], deadline_matches, strict=True)
            if not matched
        ]
        accuracy = sum(deadline_matches) / len(deadline_matches)
        coverage = len(set(ours) & {row["case_id"] for row in truth["all_open"]}) / len(
            truth["all_open"]
        )
        deterministic = [
            CheckResult(
                name="q01.kendall_tau_top_15",
                passed=tau >= 0.8,
                actual=round(tau, 3),
                expected=">=0.8",
            ),
            CheckResult(
                name="q01.top_15_overlap",
                passed=overlap >= top_n - 3,
                actual=overlap,
                expected=f">={top_n - 3}",
            ),
            CheckResult(
                name="q01.next_deadline_accuracy",
                passed=accuracy >= 0.9,
                actual=round(accuracy, 3),
                expected=">=0.9",
                detail=json.dumps(
                    {"date_mismatches": mismatches, "label_differences": label_differences}
                ),
            ),
            CheckResult(
                name="q01.fan_out_coverage", passed=coverage == 1.0, actual=coverage, expected=1.0
            ),
        ]
        capabilities = self._evaluate_capabilities(truth, events)
        counts: dict[str, int] = {}
        for event in events:
            counts[event.type] = counts.get(event.type, 0) + 1
        complete = (
            [event.seq for event in events] == list(range(1, len(events) + 1))
            and counts.get("node_entered") == counts.get("node_exited")
            and counts.get("tool_call") == counts.get("tool_result")
            and counts.get("llm_call_started")
            == counts.get("llm_call", 0) + counts.get("llm_call_failed", 0)
        )
        result = EvalResult(
            case_id="Q01",
            passed=all(check.passed for check in deterministic + capabilities) and complete,
            deterministic=deterministic,
            capabilities=capabilities,
            trajectory_complete=complete,
        )
        emitter.emit(
            EventDraft(
                actor=Actor(kind=ActorKind.EVALUATOR, name="ground_truth_evaluator"),
                type="eval_scored",
                summary=f"Q01 evaluation {'passed' if result.passed else 'failed'}",
                payload=result.model_dump(mode="json"),
                refs=["Q01"],
            )
        )
        return result

    def _load_truth(self, case_id: str) -> dict[str, Any]:
        target = (self.evaluator_root / "cases" / f"{case_id}.json").resolve()
        if self.evaluator_root not in target.parents:
            raise PermissionError("ground-truth path escapes evaluator root")
        return json.loads(target.read_text(encoding="utf-8"))

    @staticmethod
    def _evaluate_check(record: dict[str, Any], check: dict[str, Any]) -> CheckResult:
        actual = _resolve(record, check["path"])
        expected = check.get("value")
        op = check["op"]
        if op == "eq":
            passed = _equivalent(actual, expected)
        elif op == "approx":
            tolerance = float(check.get("tolerance", 0.01))
            passed = math.isclose(float(actual), float(expected), abs_tol=tolerance)
        elif op == "in":
            passed = actual in expected
        elif op == "contains":
            passed = expected in actual
        elif op == "contains_text":
            passed = str(expected).casefold() in str(actual).casefold()
        elif op == "not_contains":
            passed = expected not in actual
        elif op == "not_contains_any":
            text = json.dumps(actual).casefold()
            passed = not any(str(item).casefold() in text for item in expected)
        elif op == "set_eq":
            passed = set(actual) == set(expected)
        else:
            passed = False
        return CheckResult(
            name=f"{check['path']} {op}",
            passed=passed,
            actual=actual,
            expected=expected,
            detail="" if passed else f"operator={op}",
        )

    @staticmethod
    def _expected_subset_checks(
        record: dict[str, Any], expected: dict[str, Any]
    ) -> list[CheckResult]:
        checks: list[CheckResult] = []
        for field in ("is_dispute", "claim_family", "split_case_required"):
            if field in expected:
                checks.append(_equality_result(f"expected.{field}", record[field], expected[field]))

        for field in ("ring_members", "ring_linkage", "visa_rule_notes", "ce3_assessment"):
            if field in expected:
                actual = record.get(field)
                wanted = expected[field]
                passed = set(actual) == set(wanted) if field == "ring_members" else actual == wanted
                checks.append(
                    CheckResult(
                        name=f"expected.{field}",
                        passed=passed,
                        actual=actual,
                        expected=wanted,
                    )
                )

        if "network_actions" in expected:
            wanted_actions = expected["network_actions"]
            if not wanted_actions:
                checks.append(
                    _equality_result(
                        "expected.network_actions", record["network_actions"], wanted_actions
                    )
                )
            else:
                by_txn = {action["txn_id"]: action for action in record["network_actions"]}
                wanted_actions = [
                    {**wanted, "txn_id": txn_id}
                    for wanted in wanted_actions
                    for txn_id in expand_range(wanted["txn_id"])
                ]
                for wanted in wanted_actions:
                    actual = by_txn.get(wanted["txn_id"])
                    tolerance = float(wanted.get("amount_tolerance", 0))
                    passed = actual is not None
                    if passed:
                        for key, value in wanted.items():
                            if key == "amount_tolerance":
                                continue
                            if key == "prerequisite":
                                passed = value in actual.get("certification", [])
                                if not passed:
                                    break
                                continue
                            if key == "amount" and tolerance:
                                passed = math.isclose(
                                    float(actual[key]), float(value), abs_tol=tolerance
                                )
                            else:
                                passed = _equivalent(actual.get(key), value)
                            if not passed:
                                break
                    checks.append(
                        CheckResult(
                            name=f"expected.network_actions[{wanted['txn_id']}]",
                            passed=passed,
                            actual=actual,
                            expected=wanted,
                        )
                    )

        resolution = expected.get("cardholder_resolution", {})
        if isinstance(resolution, list):
            by_case = {row.get("case_id"): row for row in record.get("case_resolutions", [])}
            for wanted in resolution:
                actual = by_case.get(wanted["case_id"], {})
                for field, value in wanted.items():
                    if field not in {"note", "case_id"}:
                        checks.append(
                            _equality_result(
                                f"expected.cardholder_resolution[{wanted['case_id']}].{field}",
                                actual.get(field),
                                value,
                            )
                        )
        else:
            for field, wanted in resolution.items():
                if field == "note":
                    continue
                actual = record["cardholder_resolution"].get(field)
                checks.append(
                    _equality_result(f"expected.cardholder_resolution.{field}", actual, wanted)
                )

        for field, wanted in expected.get("deadlines", {}).items():
            actual = record.get("deadlines", {}).get(field)
            if isinstance(wanted, dict):
                for key, value in wanted.items():
                    checks.append(
                        _equality_result(
                            f"expected.deadlines.{field}.{key}", (actual or {}).get(key), value
                        )
                    )
            else:
                checks.append(_equality_result(f"expected.deadlines.{field}", actual, wanted))

        wait = expected.get("wait")
        if wait:
            for key in ("available_at", "latest_safe_decision_date"):
                checks.append(
                    _equality_result(
                        f"expected.wait.{key}", (record.get("wait") or {}).get(key), wait[key]
                    )
                )

        guidance = expected.get("cardholder_guidance")
        if isinstance(guidance, dict):
            for topic, wanted in guidance.items():
                actual = record.get("cardholder_guidance", {}).get(topic)
                if isinstance(wanted, dict):
                    passed = isinstance(actual, dict) and all(
                        _equivalent(actual.get(key), value) for key, value in wanted.items()
                    )
                else:
                    passed = actual == wanted
                checks.append(
                    CheckResult(
                        name=f"expected.cardholder_guidance.{topic}",
                        passed=passed,
                        actual=actual,
                        expected=wanted,
                    )
                )
        elif isinstance(guidance, list):
            rendered_guidance = json.dumps(record.get("cardholder_guidance", {})).casefold()
            for item in guidance:
                checks.append(
                    CheckResult(
                        name=f"expected.cardholder_guidance contains {item}",
                        passed=str(item).casefold() in rendered_guidance,
                        actual=record.get("cardholder_guidance", {}),
                        expected=item,
                    )
                )

        for letter in expected.get("letters", []):
            checks.append(
                CheckResult(
                    name=f"expected.letters contains {letter}",
                    passed=letter in record.get("letters", []),
                    actual=record.get("letters", []),
                    expected=letter,
                )
            )

        for account_action in expected.get("account_actions", []):
            checks.append(
                CheckResult(
                    name=f"expected.account_actions contains {account_action}",
                    passed=account_action in record.get("account_actions", []),
                    actual=record.get("account_actions", []),
                    expected=account_action,
                )
            )

        for index, wanted in enumerate(expected.get("automated_actions", [])):
            if wanted.get("optional"):
                continue
            candidates = [
                actual
                for actual in record.get("automated_actions", [])
                if actual.get("action") == wanted.get("action")
            ]
            passed = any(
                all(
                    key in {"optional", "prerequisite"} or _equivalent(actual.get(key), value)
                    for key, value in wanted.items()
                )
                for actual in candidates
            )
            checks.append(
                CheckResult(
                    name=f"expected.automated_actions[{index}]",
                    passed=passed,
                    actual=candidates,
                    expected=wanted,
                )
            )

        forbidden = expected.get("account_actions_forbidden", [])
        if forbidden:
            used = sorted(set(record.get("account_actions", [])).intersection(forbidden))
            checks.append(
                CheckResult(
                    name="expected.account_actions_forbidden",
                    passed=not used,
                    actual=used,
                    expected=[],
                )
            )

        review_required = expected.get("adjudication", {}).get("review_panel_required")
        if review_required is not None:
            checks.append(
                _equality_result(
                    "expected.adjudication.review_panel_required",
                    record["adjudication"]["review_panel_used"],
                    review_required,
                )
            )
        adjudication = expected.get("adjudication", {})
        if "min_confidence" in adjudication:
            actual = float(record["adjudication"]["confidence"])
            wanted = float(adjudication["min_confidence"])
            checks.append(
                CheckResult(
                    name="expected.adjudication.min_confidence",
                    passed=actual >= wanted,
                    actual=actual,
                    expected=wanted,
                )
            )
        if "conservative_default_applied" in adjudication:
            checks.append(
                _equality_result(
                    "expected.adjudication.conservative_default_applied",
                    record["adjudication"]["conservative_default_applied"],
                    adjudication["conservative_default_applied"],
                )
            )
        if "flip_fact" in adjudication:
            actual = record["adjudication"]["flip_fact"]
            wanted = adjudication["flip_fact"]
            checks.append(
                CheckResult(
                    name="expected.adjudication.flip_fact",
                    passed=str(actual).casefold().rstrip(".") == str(wanted).casefold().rstrip("."),
                    actual=actual,
                    expected=wanted,
                )
            )

        excluded = expected.get("must_exclude_customers", [])
        if excluded:
            rendered = json.dumps(
                {
                    "ring_members": record.get("ring_members"),
                    "automated_actions": record.get("automated_actions"),
                    "memory_ops": record.get("memory_ops"),
                }
            )
            found = [customer for customer in excluded if customer in rendered]
            checks.append(
                CheckResult(
                    name="expected.must_exclude_customers",
                    passed=not found,
                    actual=found,
                    expected=[],
                )
            )
        return checks

    @staticmethod
    def _requirement_checks(
        record: dict[str, Any], truth: dict[str, Any], events: list[EventEnvelope]
    ) -> list[CheckResult]:
        checks: list[CheckResult] = []
        cited = {citation["doc_id"] for citation in record.get("citations", [])}
        required_citations = set(truth.get("must_cite", []))
        if required_citations:
            checks.append(
                CheckResult(
                    name="must_cite",
                    passed=required_citations <= cited,
                    actual=sorted(cited),
                    expected=sorted(required_citations),
                )
            )

        rendered = json.dumps(record, sort_keys=True).casefold()
        forbidden = [
            phrase for phrase in truth.get("must_not", []) if phrase.casefold() in rendered
        ]
        if truth.get("must_not"):
            checks.append(
                CheckResult(
                    name="must_not",
                    passed=not forbidden,
                    actual=forbidden,
                    expected=[],
                )
            )

        memory = truth.get("memory_ops", {})
        if memory:
            read_ids = {
                item
                for event in events
                if event.type == "memory_read"
                for item in event.payload.get("result_ids", [])
            }
            for note_id in [
                item for entry in memory.get("read", []) for item in expand_range(entry)
            ]:
                checks.append(
                    CheckResult(
                        name=f"memory_ops.read[{note_id}]",
                        passed=note_id in read_ids,
                        actual=sorted(read_ids),
                        expected=note_id,
                    )
                )
            superseded = {
                event.payload.get("target_id")
                for event in events
                if event.type == "memory_supersede"
            }
            for operation in memory.get("supersede", []):
                note_id = operation["note_id"]
                checks.append(
                    CheckResult(
                        name=f"memory_ops.supersede[{note_id}]",
                        passed=note_id in superseded,
                        actual=sorted(item for item in superseded if item),
                        expected=note_id,
                    )
                )
            for event_type, operation_name in (
                ("memory_retract", "retract"),
                ("memory_consolidate", "consolidate"),
            ):
                observed = [event for event in events if event.type == event_type]
                for operation in memory.get(operation_name, []):
                    if "from_notes" in operation:
                        checks.append(_consolidation_check(operation, observed))
                        continue
                    target = operation.get("note_id") or operation.get("into")
                    passed = any(
                        event.payload.get("target_id") == target
                        or str(event.payload.get("target_id", "")).startswith(str(target))
                        for event in observed
                    )
                    checks.append(
                        CheckResult(
                            name=f"memory_ops.{operation_name}[{target}]",
                            passed=passed,
                            actual=[event.payload.get("target_id") for event in observed],
                            expected=target,
                        )
                    )
            state_change_events = [
                event
                for event in events
                if event.type
                in {
                    "memory_write",
                    "memory_supersede",
                    "memory_retract",
                    "memory_consolidate",
                    "graph_write",
                    "automated_action",
                }
            ]
            writes = json.dumps(
                {
                    "events": [event.payload for event in state_change_events],
                    "memory_ops": record.get("memory_ops", []),
                    "account_actions": record.get("account_actions", []),
                    "automated_actions": record.get("automated_actions", []),
                    "ring_members": record.get("ring_members", []),
                }
            ).casefold()
            for forbidden_write in memory.get("must_not_write", []):
                lowered = forbidden_write.casefold()
                if "fraud report" in lowered:
                    violated = "fraud_report" in writes
                elif "card reissue" in lowered:
                    violated = "card_reissue" in writes
                elif "suspectedring" in lowered and "cus-90017" in lowered:
                    violated = "cus-90017" in writes and "suspectedring" in writes
                elif "account closure or restriction" in lowered:
                    violated = any(
                        action in writes
                        for action in ("close_account", "restrict_account", "account_closure")
                    )
                elif "customer risk or fraud note" in lowered:
                    violated = any(
                        event.type == "memory_write"
                        and event.payload.get("scope") == "customer"
                        and any(
                            word in json.dumps(event.payload).casefold()
                            for word in ("risk", "fraudster", "misuse")
                        )
                        for event in state_change_events
                    )
                else:
                    violated = lowered in writes
                checks.append(
                    CheckResult(
                        name=f"memory_ops.must_not_write[{forbidden_write}]",
                        passed=not violated,
                        actual="violation" if violated else "absent",
                        expected="absent",
                    )
                )
        return checks

    @staticmethod
    def _evaluate_capabilities(
        truth: dict[str, Any], events: list[EventEnvelope]
    ) -> list[CheckResult]:
        event_types = {event.type for event in events}
        results: list[CheckResult] = []
        for requirement in truth.get("required_capabilities", []):
            if requirement.get("necessity") != "primary":
                continue
            raw_signals = requirement.get(
                "trajectory_signals",
                requirement.get("trajectory_events", requirement.get("signals", [])),
            )
            signals = sorted(
                {signal_type for signal in raw_signals for signal_type in _signal_types(signal)}
            )
            observed = sorted(event_types.intersection(signals))
            passed = bool(signals) and bool(observed)
            results.append(
                CheckResult(
                    name=requirement["capability"],
                    passed=passed,
                    actual=observed,
                    expected=signals,
                    detail="" if passed else "none of the trajectory signals were observed",
                )
            )
        return results

    @staticmethod
    def _trajectory_complete(events: list[EventEnvelope]) -> bool:
        counts: dict[str, int] = {}
        for event in events:
            counts[event.type] = counts.get(event.type, 0) + 1
        span_ids = {event.span_id for event in events}
        parents_valid = all(
            event.parent_span_id in span_ids for event in events if event.parent_span_id
        )
        return (
            bool(events)
            and [event.seq for event in events] == list(range(1, len(events) + 1))
            and counts.get("node_entered") == counts.get("node_exited")
            and counts.get("tool_call") == counts.get("tool_result")
            and counts.get("llm_call_started")
            == counts.get("llm_call", 0) + counts.get("llm_call_failed", 0)
            and counts.get("decision_recorded") == 1
            and parents_valid
        )


def _kendall_tau(ranks: list[int]) -> float:
    """Kendall rank correlation between the expected order and the observed ranks."""

    pairs = [(ranks[i], ranks[j]) for i in range(len(ranks)) for j in range(i + 1, len(ranks))]
    if not pairs:
        return 0.0
    concordant = sum(1 for left, right in pairs if left < right)
    return (2 * concordant - len(pairs)) / len(pairs)


def _consolidation_check(operation: dict[str, Any], observed: list[EventEnvelope]) -> CheckResult:
    """A consolidation archives the named notes into one note with the expected scope and window."""

    wanted = set(operation["from_notes"])
    matches = [
        event.payload
        for event in observed
        if wanted <= set(event.payload.get("from_ids", []))
        and set(operation.get("subject_ids", [])) <= set(event.payload.get("subject_ids", []))
        and all(
            (event.payload.get("validity") or {}).get(key) == operation[key]
            for key in ("valid_from", "valid_to")
            if key in operation
        )
    ]
    return CheckResult(
        name=f"memory_ops.consolidate[{min(wanted)}..{max(wanted)}]",
        passed=bool(matches),
        actual=[
            {
                key: event.payload.get(key)
                for key in ("target_id", "from_ids", "subject_ids", "validity")
            }
            for event in observed
        ],
        expected=operation,
    )


_RANGE_RE = re.compile(r"^(?P<prefix>[A-Z]+-)(?P<start>\d+)\.\.(?P=prefix)(?P<end>\d+)$")


def expand_range(value: str) -> list[str]:
    """Expand ground-truth ranges such as TXN-9001001..TXN-9001023 or MEM-0201..MEM-0208."""

    match = _RANGE_RE.match(value)
    if not match:
        return [value]
    width = len(match.group("start"))
    start, end = int(match.group("start")), int(match.group("end"))
    return [f"{match.group('prefix')}{number:0{width}d}" for number in range(start, end + 1)]


_FILTER_RE = re.compile(r"^(?P<name>[^[]+)\[\?(?P<key>[^=]+)==['\"](?P<value>[^'\"]+)['\"]\]$")
_INDEX_RE = re.compile(r"^(?P<name>[^[]+)\[(?P<index>\d+)\]$")
_WILDCARD_RE = re.compile(r"^(?P<name>[^[]+)\[\*\]$")


def _resolve(value: Any, path: str) -> Any:
    current = value
    for part in path.removeprefix("$.").split("."):
        match = _FILTER_RE.match(part)
        if match:
            rows = current[match.group("name")]
            current = next(
                row for row in rows if str(row.get(match.group("key"))) == match.group("value")
            )
        elif wildcard_match := _WILDCARD_RE.match(part):
            current = current[wildcard_match.group("name")]
        elif index_match := _INDEX_RE.match(part):
            current = current[index_match.group("name")][int(index_match.group("index"))]
        elif isinstance(current, list) and part.isdigit():
            current = current[int(part)]
        elif isinstance(current, list):
            current = [row[part] for row in current if isinstance(row, dict) and part in row]
        else:
            current = current[part]
    return current


def _signal_types(signal: Any) -> list[str]:
    if isinstance(signal, dict):
        return [str(signal.get("type", ""))]
    prefix = str(signal).split("{", 1)[0]
    underscored = re.findall(r"\b[a-z][a-z0-9]*_[a-z0-9_*]+\b", prefix)
    leading = [segment.strip().split()[0] for segment in prefix.split("/") if segment.strip()]
    return list(dict.fromkeys([*underscored, *leading]))


def _equivalent(actual: Any, expected: Any) -> bool:
    try:
        return float(actual) == float(expected)
    except (TypeError, ValueError):
        return actual == expected


def _equality_result(name: str, actual: Any, expected: Any) -> CheckResult:
    return CheckResult(
        name=name,
        passed=_equivalent(actual, expected),
        actual=actual,
        expected=expected,
    )
