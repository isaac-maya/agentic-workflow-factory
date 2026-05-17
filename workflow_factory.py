"""Agentic workflow registry, policy-driven guardrails, and monitoring report."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).parent
WORKFLOWS_PATH = ROOT / "workflows.yaml"
EVENTS_PATH = ROOT / "sample_inputs" / "events.json"
REPORT_PATH = ROOT / "monitoring_report.md"


@dataclass(frozen=True)
class Guardrail:
    """A policy that can block or flag a specific step on a given event."""
    applies_to: str
    severity: str            # "block" or "flag"
    description: str
    check: Callable[[dict], bool]   # returns True when the event is acceptable


VARIANCE_THRESHOLD_PCT = 10.0


GUARDRAILS: dict[str, Guardrail] = {
    "require_customer_context": Guardrail(
        applies_to="retrieve_customer_context",
        severity="block",
        description="customer context must be present before routing",
        check=lambda event: bool(event.get("customer_context", False)),
    ),
    "block_customer_message_without_review": Guardrail(
        applies_to="draft_status_update",
        severity="block",
        description="customer-facing message blocked when unsafe action is requested",
        check=lambda event: not event.get("unsafe_action_requested", False),
    ),
    "require_variance_threshold": Guardrail(
        applies_to="compare_baseline",
        severity="block",
        description=f"variance must reach {VARIANCE_THRESHOLD_PCT}% before investigation",
        check=lambda event: event.get("variance_pct", 0) >= VARIANCE_THRESHOLD_PCT,
    ),
    "block_financial_adjustment": Guardrail(
        applies_to="notify_ops_channel",
        severity="block",
        description="financial adjustment notification blocked without explicit approval",
        check=lambda event: not event.get("unsafe_action_requested", False),
    ),
    "require_human_priority_review": Guardrail(
        applies_to="assign_priority",
        severity="flag",
        description="priority assignment requires human review before commit",
        check=lambda event: True,
    ),
    "block_auto_close": Guardrail(
        applies_to="prepare_triage_summary",
        severity="block",
        description="auto-close attempts blocked; require ticket owner action",
        check=lambda event: not event.get("auto_close_requested", False),
    ),
}


def _strip_value(raw: str) -> str:
    return raw.strip().strip('"')


def load_workflows() -> dict[str, dict]:
    workflows: dict[str, dict] = {}
    current: dict | None = None
    active_list: str | None = None

    for raw_line in WORKFLOWS_PATH.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped == "workflows:":
            continue

        if stripped.startswith("- id:"):
            if current is not None:
                workflows[current["id"]] = current
            current = {
                "id": _strip_value(stripped.split(":", 1)[1]),
                "owner": "",
                "trigger": "",
                "steps": [],
                "guardrails": [],
            }
            active_list = None
            continue

        if current is None:
            continue

        if stripped.startswith("steps:"):
            active_list = "steps"
            continue
        if stripped.startswith("guardrails:"):
            active_list = "guardrails"
            continue

        if stripped.startswith("owner:"):
            current["owner"] = _strip_value(stripped.split(":", 1)[1])
            continue
        if stripped.startswith("trigger:"):
            current["trigger"] = _strip_value(stripped.split(":", 1)[1])
            continue

        if stripped.startswith("- ") and active_list:
            current[active_list].append(_strip_value(stripped[2:]))

    if current is not None:
        workflows[current["id"]] = current

    return workflows


def evaluate_step(step: str, workflow: dict, event: dict) -> tuple[str, str | None, str | None]:
    """Apply every guardrail attached to the workflow that targets this step.

    Returns (status, guardrail_name, reason). status is one of:
        ok, blocked, flagged
    """
    for guardrail_name in workflow["guardrails"]:
        guardrail = GUARDRAILS.get(guardrail_name)
        if guardrail is None or guardrail.applies_to != step:
            continue
        if not guardrail.check(event):
            return (
                "blocked" if guardrail.severity == "block" else "flagged",
                guardrail_name,
                guardrail.description,
            )
        if guardrail.severity == "flag":
            return "flagged", guardrail_name, guardrail.description
    return "ok", None, None


def execute_event(event: dict, workflow: dict) -> dict:
    trace: list[dict] = []
    blocked_by: list[str] = []
    flagged_by: list[str] = []
    halted = False

    for step in workflow["steps"]:
        if halted:
            trace.append({"step": step, "status": "skipped", "reason": "halted by prior block"})
            continue
        status, guardrail_name, reason = evaluate_step(step, workflow, event)
        trace.append({
            "step": step,
            "status": status,
            "guardrail": guardrail_name,
            "reason": reason,
        })
        if status == "blocked":
            blocked_by.append(guardrail_name or "")
            halted = True
        elif status == "flagged":
            flagged_by.append(guardrail_name or "")

    return {
        "event_id": event["event_id"],
        "workflow_id": event["workflow_id"],
        "owner": workflow["owner"],
        "trigger": workflow["trigger"],
        "trace": trace,
        "blocked": bool(blocked_by),
        "blocked_by": blocked_by,
        "flagged": bool(flagged_by),
        "flagged_by": flagged_by,
        "completed": not blocked_by,
    }


def per_workflow_summary(results: list[dict], workflows: dict[str, dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for result in results:
        grouped[result["workflow_id"]].append(result)
    rows = []
    for workflow_id in sorted(grouped):
        runs = grouped[workflow_id]
        rows.append({
            "workflow_id": workflow_id,
            "owner": workflows[workflow_id]["owner"],
            "runs": len(runs),
            "completed": sum(1 for r in runs if r["completed"]),
            "blocked": sum(1 for r in runs if r["blocked"]),
            "flagged": sum(1 for r in runs if r["flagged"]),
        })
    return rows


def guardrail_effectiveness(results: list[dict]) -> list[dict]:
    fired: Counter[str] = Counter()
    by_severity: dict[str, str] = {}
    examples: dict[str, list[str]] = defaultdict(list)
    for result in results:
        for step_record in result["trace"]:
            name = step_record.get("guardrail")
            if not name:
                continue
            if step_record["status"] == "blocked":
                fired[name] += 1
                by_severity[name] = "block"
                examples[name].append(result["event_id"])
            elif step_record["status"] == "flagged":
                fired[name] += 1
                by_severity[name] = by_severity.get(name, "flag")
                examples[name].append(result["event_id"])
    rows = []
    for name, count in fired.most_common():
        guardrail = GUARDRAILS.get(name)
        rows.append({
            "guardrail": name,
            "severity": by_severity[name],
            "fired": count,
            "description": guardrail.description if guardrail else "(unknown)",
            "events": sorted(set(examples[name])),
        })
    return rows


def render_workflow_table(rows: list[dict]) -> list[str]:
    lines = [
        "| Workflow | Owner | Runs | Completed | Blocked | Flagged |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['workflow_id']}` | {row['owner']} | {row['runs']} | "
            f"{row['completed']} | {row['blocked']} | {row['flagged']} |"
        )
    return lines


def render_guardrail_table(rows: list[dict]) -> list[str]:
    if not rows:
        return ["_No guardrails fired in this window._"]
    lines = [
        "| Guardrail | Severity | Fired | Events | Description |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for row in rows:
        events = ", ".join(row["events"])
        lines.append(
            f"| `{row['guardrail']}` | {row['severity']} | {row['fired']} | {events} | {row['description']} |"
        )
    return lines


def render_trace(result: dict) -> list[str]:
    lines = [
        f"### {result['event_id']} / `{result['workflow_id']}`",
        "",
        f"Owner: {result['owner']} | Trigger: `{result['trigger']}` | "
        f"Outcome: {'completed' if result['completed'] else 'blocked'}",
        "",
    ]
    for step_record in result["trace"]:
        status = step_record["status"]
        line = f"- {step_record['step']}: **{status}**"
        if step_record.get("guardrail"):
            line += f" ({step_record['guardrail']}: {step_record['reason']})"
        elif step_record.get("reason"):
            line += f" ({step_record['reason']})"
        lines.append(line)
    lines.append("")
    return lines


def render_report(results: list[dict], workflows: dict[str, dict]) -> str:
    workflow_rows = per_workflow_summary(results, workflows)
    guardrail_rows = guardrail_effectiveness(results)
    total_blocked = sum(1 for result in results if result["blocked"])
    total_flagged = sum(1 for result in results if result["flagged"])

    lines = [
        "# Agentic Workflow Monitoring Report",
        "",
        "## Sendable Summary",
        "",
        "This report shows the workflow factory operating as a policy-driven system: each workflow declares which guardrails apply, the runner evaluates them against the incoming event, and the monitoring view tracks which guardrails are actually doing work. Guardrails are the policy contract — the YAML defines them, the code enforces them, and the report makes the activity reviewable.",
        "",
        "## Summary",
        "",
        f"- Events processed: {len(results)}",
        f"- Workflows completed: {sum(1 for r in results if r['completed'])}",
        f"- Workflows blocked by guardrails: {total_blocked}",
        f"- Workflows flagged for human review: {total_flagged}",
        "",
        "## Per-Workflow Summary",
        "",
        *render_workflow_table(workflow_rows),
        "",
        "## Guardrail Effectiveness",
        "",
        "This is the monitoring view a SaaS operations team would actually want: which guardrails fired, on which events, and what they protect against. A guardrail that never fires is a candidate for deprecation; one that fires constantly is a candidate for promotion to a real product fix upstream.",
        "",
        *render_guardrail_table(guardrail_rows),
        "",
        "## Event Traces",
        "",
    ]
    for result in results:
        lines.extend(render_trace(result))

    lines.extend([
        "## Monitoring Takeaway",
        "",
        "The factory keeps three properties visible at once: the workflow registry (what we automate), the guardrail registry (what we refuse to automate without review), and the runtime behavior (which guardrails are doing the work). That separation is what makes prototypes safe to graduate into production-ready agentic workflows.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    workflows = load_workflows()
    events = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    results = [execute_event(event, workflows[event["workflow_id"]]) for event in events]
    REPORT_PATH.write_text(render_report(results, workflows), encoding="utf-8")
    blocked = sum(1 for r in results if r["blocked"])
    flagged = sum(1 for r in results if r["flagged"])
    print(f"Processed {len(results)} workflow events: {blocked} blocked, {flagged} flagged.")


if __name__ == "__main__":
    main()
