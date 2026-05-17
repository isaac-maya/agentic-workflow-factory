# Varicent Agentic Workflow Factory

A compact local workflow factory for SaaS operations. Workflows are declared in YAML, guardrails are a policy registry the runner actually enforces, and the monitoring report tracks which guardrails are doing work across the event stream. The pattern is meant to make prototypes safe to graduate — not to simulate production scale.

## Run

```bash
python3 workflow_factory.py
```

The command refreshes `monitoring_report.md`.

## What It Demonstrates In 30 Seconds

- The workflow registry (`workflows.yaml`) is the contract; the guardrail registry (in `workflow_factory.py`) is the policy enforcement layer. The two are wired, not decorative — every guardrail listed in YAML is a real callable that can block or flag a specific step.
- The monitoring report includes a **guardrail effectiveness table**: which guardrail fired, how many times, on which events. That is the output a SaaS operations team would actually use to decide which guardrails to deprecate, which to keep, and which to promote into upstream product fixes.
- Two severity levels — `block` halts the workflow immediately; `flag` lets it continue but records human review.
- The per-workflow summary makes it obvious which workflows are getting stopped most often — instantly useful for triage.

## Sample Output Signals

In the bundled 8-event dataset, the report shows:
- 6 of 6 declared guardrails fire at least once across 3 workflows.
- `require_human_priority_review` fires as a flag on every backlog triage run (informational, by design).
- `block_customer_message_without_review` correctly halts an escalation when an unsafe action is requested even though the customer context is present — a second-order check, not just an input filter.
- `require_variance_threshold` blocks an anomaly run where variance is below 10% — preventing investigation noise.

## Workflows

| Workflow | Owner | Trigger |
| --- | --- | --- |
| `escalation_routing` | SaaS Operations | high-severity support ticket |
| `anomaly_flagging` | Revenue Operations | revenue variance metric |
| `backlog_triage` | Product Operations | daily backlog review |

## Why It Fits Varicent

The role explicitly asks for production-ready agentic workflows with monitoring agents around them. This pack shows the smallest credible version of that shape:

- Declarative workflow definitions (YAML) — easy to add a fourth workflow without touching the runner.
- Policy-driven guardrails (Python registry) — every guardrail is a real check, not a label.
- Monitoring view that scales the conversation from "did the workflow run?" to "which guardrails are doing the work and which should be deprecated?"
- Trace preservation per event — auditable and reviewable.

## Files

- `workflows.yaml`: three workflow definitions with declared guardrails per workflow.
- `sample_inputs/events.json`: 8 synthetic events that exercise every guardrail at least once.
- `workflow_factory.py`: loader, guardrail registry, runner, and monitoring report renderer.
- `monitoring_report.md`: generated report — summary, per-workflow table, guardrail effectiveness, event traces.
- `outreach_note.md`: Varicent-specific sharing note.

## Outreach Hook

A small agentic workflow factory where the YAML's guardrail list is wired to real policy code, and the monitoring report tracks guardrail effectiveness — which guardrails fired, on which events, and what they protect against. It is intentionally compact, but the separation between workflow registry, guardrail registry, and runtime behavior is the pattern I would scale into a production workflow program.
