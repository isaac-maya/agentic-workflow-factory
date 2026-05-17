# Agentic Workflow Monitoring Report

## Sendable Summary

This report shows the workflow factory operating as a policy-driven system: each workflow declares which guardrails apply, the runner evaluates them against the incoming event, and the monitoring view tracks which guardrails are actually doing work. Guardrails are the policy contract — the YAML defines them, the code enforces them, and the report makes the activity reviewable.

## Summary

- Events processed: 8
- Workflows completed: 3
- Workflows blocked by guardrails: 5
- Workflows flagged for human review: 2

## Per-Workflow Summary

| Workflow | Owner | Runs | Completed | Blocked | Flagged |
| --- | --- | ---: | ---: | ---: | ---: |
| `anomaly_flagging` | Revenue Operations | 3 | 1 | 2 | 0 |
| `backlog_triage` | Product Operations | 2 | 1 | 1 | 2 |
| `escalation_routing` | SaaS Operations | 3 | 1 | 2 | 0 |

## Guardrail Effectiveness

This is the monitoring view a SaaS operations team would actually want: which guardrails fired, on which events, and what they protect against. A guardrail that never fires is a candidate for deprecation; one that fires constantly is a candidate for promotion to a real product fix upstream.

| Guardrail | Severity | Fired | Events | Description |
| --- | --- | ---: | --- | --- |
| `require_human_priority_review` | flag | 2 | evt-007, evt-008 | priority assignment requires human review before commit |
| `require_customer_context` | block | 1 | evt-002 | customer context must be present before routing |
| `block_customer_message_without_review` | block | 1 | evt-003 | customer-facing message blocked when unsafe action is requested |
| `block_financial_adjustment` | block | 1 | evt-005 | financial adjustment notification blocked without explicit approval |
| `require_variance_threshold` | block | 1 | evt-006 | variance must reach 10.0% before investigation |
| `block_auto_close` | block | 1 | evt-008 | auto-close attempts blocked; require ticket owner action |

## Event Traces

### evt-001 / `escalation_routing`

Owner: SaaS Operations | Trigger: `support_ticket.severity_high` | Outcome: completed

- classify_ticket: **ok**
- retrieve_customer_context: **ok**
- route_to_owner: **ok**
- draft_status_update: **ok**

### evt-002 / `escalation_routing`

Owner: SaaS Operations | Trigger: `support_ticket.severity_high` | Outcome: blocked

- classify_ticket: **ok**
- retrieve_customer_context: **blocked** (require_customer_context: customer context must be present before routing)
- route_to_owner: **skipped** (halted by prior block)
- draft_status_update: **skipped** (halted by prior block)

### evt-003 / `escalation_routing`

Owner: SaaS Operations | Trigger: `support_ticket.severity_high` | Outcome: blocked

- classify_ticket: **ok**
- retrieve_customer_context: **ok**
- route_to_owner: **ok**
- draft_status_update: **blocked** (block_customer_message_without_review: customer-facing message blocked when unsafe action is requested)

### evt-004 / `anomaly_flagging`

Owner: Revenue Operations | Trigger: `metric.revenue_variance` | Outcome: completed

- compare_baseline: **ok**
- identify_impacted_accounts: **ok**
- create_investigation_task: **ok**
- notify_ops_channel: **ok**

### evt-005 / `anomaly_flagging`

Owner: Revenue Operations | Trigger: `metric.revenue_variance` | Outcome: blocked

- compare_baseline: **ok**
- identify_impacted_accounts: **ok**
- create_investigation_task: **ok**
- notify_ops_channel: **blocked** (block_financial_adjustment: financial adjustment notification blocked without explicit approval)

### evt-006 / `anomaly_flagging`

Owner: Revenue Operations | Trigger: `metric.revenue_variance` | Outcome: blocked

- compare_baseline: **blocked** (require_variance_threshold: variance must reach 10.0% before investigation)
- identify_impacted_accounts: **skipped** (halted by prior block)
- create_investigation_task: **skipped** (halted by prior block)
- notify_ops_channel: **skipped** (halted by prior block)

### evt-007 / `backlog_triage`

Owner: Product Operations | Trigger: `backlog.daily_review` | Outcome: completed

- cluster_requests: **ok**
- detect_duplicates: **ok**
- assign_priority: **flagged** (require_human_priority_review: priority assignment requires human review before commit)
- prepare_triage_summary: **ok**

### evt-008 / `backlog_triage`

Owner: Product Operations | Trigger: `backlog.daily_review` | Outcome: blocked

- cluster_requests: **ok**
- detect_duplicates: **ok**
- assign_priority: **flagged** (require_human_priority_review: priority assignment requires human review before commit)
- prepare_triage_summary: **blocked** (block_auto_close: auto-close attempts blocked; require ticket owner action)

## Monitoring Takeaway

The factory keeps three properties visible at once: the workflow registry (what we automate), the guardrail registry (what we refuse to automate without review), and the runtime behavior (which guardrails are doing the work). That separation is what makes prototypes safe to graduate into production-ready agentic workflows.
