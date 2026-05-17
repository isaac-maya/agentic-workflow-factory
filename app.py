"""Streamlit app for the Agentic Workflow Factory.

Wraps workflow_factory.execute_event() so visitors can pick a workflow, build an event,
and watch the pipeline execute step-by-step with guardrails firing in real time.
Separate Monitoring tab shows guardrail effectiveness across all runs in the session.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

import streamlit as st

from workflow_factory import (
    GUARDRAILS,
    execute_event,
    guardrail_effectiveness,
    load_workflows,
)

ROOT = Path(__file__).parent
EVENTS_PATH = ROOT / "sample_inputs" / "events.json"

st.set_page_config(
    page_title="Agentic Workflow Factory — Isaac Maya",
    page_icon="🛡️",
    layout="wide",
)

# ---------- Hero ----------
st.title("🛡️ Agentic Workflow Factory")
st.markdown(
    "**Agentic workflows with guardrails that visibly do their job.**  \n"
    "_Built to demonstrate: Agentic AI Engineer · Platform Engineer · SaaS Operations_"
)

# ---------- Why ----------
with st.expander("📖 Why this exists", expanded=True):
    st.markdown(
        """
The hardest question in agentic AI right now: **how do you let agents act without setting the
building on fire?**

Most demos either skip guardrails entirely or treat them as a checkbox. This factory shows the
production answer:

- Workflows declared in **YAML** — reviewable by non-engineers.
- Guardrails declared **separately** from workflows — composable, reusable.
- **Two severities that mean different things:** `block` halts the pipeline, `flag` continues with a
  review marker. Conflating them is the most common reason guardrails get ignored in production.
- A **monitoring view** that tells you which guardrails are doing real work — and which are dead
  weight ready for deprecation.
"""
    )

with st.expander("🎯 What you're looking at"):
    st.markdown(
        """
- ✅ **Workflow registry** in YAML — declarative, reviewable, version-controllable
- ✅ **Guardrail registry** separate from workflows — composable across pipelines
- ✅ **Two severities** — `block` halts execution; `flag` continues with reviewer marker
- ✅ **Live execution trace** — every step shows ok / flagged / blocked status with reason
- ✅ **Monitoring tab** — which guardrails fired, on which events, lifecycle suggestions
- ✅ **Three real workflows** — escalation routing, anomaly flagging, backlog triage
"""
    )

# ---------- Load workflows ----------
workflows = load_workflows()
sample_events = json.loads(EVENTS_PATH.read_text())
events_by_id = {e["event_id"]: e for e in sample_events}

# ---------- Session state for run history ----------
if "run_history" not in st.session_state:
    st.session_state.run_history = []

# ---------- Tabs ----------
tab_run, tab_monitor = st.tabs(["🚀 Run a workflow", "📈 Monitoring dashboard"])

# ============================================================
# TAB 1 — Run a workflow
# ============================================================
with tab_run:
    st.header("Pick a workflow")
    wf_cols = st.columns(len(workflows))
    workflow_ids = list(workflows.keys())
    if "selected_wf" not in st.session_state:
        st.session_state.selected_wf = workflow_ids[0]

    for col, wf_id in zip(wf_cols, workflow_ids):
        wf = workflows[wf_id]
        if col.button(f"**{wf_id}**\n\n_{wf['owner']}_", key=f"wf_{wf_id}", use_container_width=True):
            st.session_state.selected_wf = wf_id

    selected = workflows[st.session_state.selected_wf]
    st.markdown(f"### Selected: `{selected['id']}`")
    st.caption(f"Owner: **{selected['owner']}** · Trigger: `{selected['trigger']}`")

    col_pipeline, col_event = st.columns([1, 1])

    with col_pipeline:
        st.subheader("Pipeline steps")
        for i, step in enumerate(selected["steps"], 1):
            relevant_guards = [g for g in selected["guardrails"] if GUARDRAILS[g].applies_to == step]
            guard_chips = " ".join(
                f"`🛡️ {g}`" + (" 🔴" if GUARDRAILS[g].severity == "block" else " 🟡")
                for g in relevant_guards
            )
            st.markdown(f"**{i}.** `{step}` {guard_chips}")
        st.caption("🔴 = block (halts pipeline)  ·  🟡 = flag (continues with review marker)")

    with col_event:
        st.subheader("Build an event")
        st.caption("👈 Load a sample, or toggle the fields below to construct your own.")

        relevant_samples = [e["event_id"] for e in sample_events if e["workflow_id"] == selected["id"]]
        sample_pick = st.selectbox("Load a sample event", options=["(custom)"] + relevant_samples)

        if sample_pick != "(custom)":
            template = events_by_id[sample_pick].copy()
        else:
            template = {"event_id": f"evt-custom-{int(time.time()) % 10000}", "workflow_id": selected["id"]}

        event_id = st.text_input("event_id", value=template.get("event_id", ""))

        event = {"event_id": event_id, "workflow_id": selected["id"]}
        if selected["id"] == "escalation_routing":
            event["customer_context"] = st.toggle(
                "customer_context present?", value=template.get("customer_context", True),
                help="If off, `require_customer_context` will BLOCK at step `retrieve_customer_context`.",
            )
            event["unsafe_action_requested"] = st.toggle(
                "unsafe_action_requested?", value=template.get("unsafe_action_requested", False),
                help="If on, `block_customer_message_without_review` will BLOCK at step `draft_status_update`.",
            )
        elif selected["id"] == "anomaly_flagging":
            event["variance_pct"] = st.slider(
                "variance_pct", min_value=0.0, max_value=50.0, value=float(template.get("variance_pct", 12.0)),
                step=0.1, help="Below 10% will BLOCK at `compare_baseline` via `require_variance_threshold`.",
            )
            event["unsafe_action_requested"] = st.toggle(
                "unsafe_action_requested?", value=template.get("unsafe_action_requested", False),
                help="If on, `block_financial_adjustment` will BLOCK at `notify_ops_channel`.",
            )
            event["impacted_accounts"] = st.number_input(
                "impacted_accounts (informational)", min_value=0, value=int(template.get("impacted_accounts", 10)),
            )
        elif selected["id"] == "backlog_triage":
            event["auto_close_requested"] = st.toggle(
                "auto_close_requested?", value=template.get("auto_close_requested", False),
                help="If on, `block_auto_close` will BLOCK at `prepare_triage_summary`.",
            )
            event["items"] = st.number_input("items (informational)", min_value=0, value=int(template.get("items", 20)))
            event["duplicates"] = st.number_input("duplicates (informational)", min_value=0, value=int(template.get("duplicates", 3)))

        if st.button("▶️ Run pipeline", use_container_width=True, type="primary"):
            placeholder = st.empty()
            result = execute_event(event, selected)
            displayed_lines = []
            for step_record in result["trace"]:
                status = step_record["status"]
                icon = {"ok": "✅", "flagged": "🟡", "blocked": "🛑", "skipped": "⏭️"}[status]
                line = f"{icon} **{step_record['step']}** — _{status}_"
                if step_record.get("guardrail"):
                    line += f"  \n   ↪ guardrail `{step_record['guardrail']}`: {step_record['reason']}"
                elif step_record.get("reason"):
                    line += f"  \n   ↪ {step_record['reason']}"
                displayed_lines.append(line)
                placeholder.markdown("\n\n".join(displayed_lines))
                time.sleep(0.4)

            st.session_state.run_history.append(result)

            if result["blocked"]:
                st.error(f"🛑 **BLOCKED** — pipeline halted by `{', '.join(result['blocked_by'])}`. No downstream action taken.")
            elif result["flagged"]:
                st.warning(f"🟡 **COMPLETED WITH FLAGS** — review required: `{', '.join(result['flagged_by'])}`.")
            else:
                st.success("✅ **COMPLETED** — no guardrails fired.")

# ============================================================
# TAB 2 — Monitoring dashboard
# ============================================================
with tab_monitor:
    st.header("Guardrail effectiveness across this session")
    history = st.session_state.run_history
    st.caption(f"Runs in this session: **{len(history)}**. Run more pipelines on the other tab to populate this view.")

    if not history:
        st.info("👈 Go to the Run tab and execute at least one workflow to see monitoring data.")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total runs", len(history))
        col2.metric("Blocked", sum(1 for r in history if r["blocked"]))
        col3.metric("Flagged", sum(1 for r in history if r["flagged"]))

        rows = guardrail_effectiveness(history)
        all_guards = set(GUARDRAILS.keys())
        fired_guards = {r["guardrail"] for r in rows}
        never_fired = sorted(all_guards - fired_guards)

        st.subheader("Guardrails that fired")
        if rows:
            import pandas as pd
            df = pd.DataFrame([
                {
                    "Guardrail": r["guardrail"],
                    "Severity": r["severity"],
                    "Fired": r["fired"],
                    "Events": ", ".join(r["events"]),
                    "Description": r["description"],
                    "Lifecycle suggestion": (
                        "🔥 Frequent — consider promoting to upstream fix"
                        if r["fired"] >= max(3, len(history) // 2)
                        else "✅ Working as intended"
                    ),
                }
                for r in rows
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.write("_No guardrails have fired yet._")

        if never_fired:
            st.subheader("Guardrails that never fired in this session")
            st.write(
                "These are candidates for deprecation — or you just haven't exercised the right input yet:\n\n"
                + "\n".join(f"- `{g}` — _{GUARDRAILS[g].description}_" for g in never_fired)
            )
        st.caption(
            "**Lifecycle thinking:** a guardrail that never fires is either deprecation-ready or under-tested. "
            "A guardrail that fires every run is screaming for an upstream product fix. The monitor surfaces both."
        )

# ============================================================
# How to test + footer
# ============================================================
st.divider()
with st.expander("🧪 How to test it (guided tour)", expanded=True):
    st.markdown(
        """
**Step 1 — Run a clean pipeline.** Pick **escalation_routing**, load sample `evt-001`, hit Run. All steps
turn ✅. Pipeline completes. Boring — that's the happy path.

**Step 2 — Trigger a BLOCK (severity = block).** Same workflow, toggle `customer_context` OFF. Run.
Watch `require_customer_context` BLOCK at step 2. Pipeline halts — the customer-facing message at step 4
is never drafted. This is the safety story.

**Step 3 — Trigger a different block.** Toggle `customer_context` back ON, toggle `unsafe_action_requested`
ON. Run. Different guardrail (`block_customer_message_without_review`) fires later in the pipeline — at the
exact step that would send the customer message. The factory caught it at the right boundary.

**Step 4 — Trigger a FLAG (severity = flag, continues).** Switch to **backlog_triage**, load `evt-007`. Run.
You'll see `require_human_priority_review` mark step 3 🟡 — but the pipeline keeps going. That's the
flag-vs-block distinction in action.

**Step 5 — Visit the Monitoring tab.** After 3+ runs, the guardrail-effectiveness table shows which rules
are doing the work. The lifecycle column suggests deprecation or promotion. This is the operations view.

**Step 6 — Read `workflows.yaml`.** The whole policy contract is ~30 lines of YAML. That's the point —
when policy is reviewable by non-engineers, the guardrails actually stay current.
"""
    )

with st.expander("💼 What this proves about me"):
    st.markdown(
        """
**For Agentic AI Engineer roles:** I separate workflow definition from guardrail policy. Composability
matters — the same guardrail (`block_customer_message_without_review`) can protect any workflow that
sends customer messages.

**For Platform Engineer roles:** The monitoring view drives policy *lifecycle*, not just observability.
Never-fired guardrails are deprecation candidates; always-fired guardrails are upstream-fix candidates.
That feedback loop is what makes a guardrail registry survive past month three.

**For SaaS Operations roles:** I write guardrails the operations team can review without an engineer
present. The YAML is the contract; the code enforces it; the monitor reports activity.

---

**Isaac Maya** — QA · Agentic AI · Data Quality  \n
📧 theisaacmaya@icloud.com · 💼 [LinkedIn](https://linkedin.com/in/isaac-maya) · 🔗 [Source](https://github.com/isaac-maya/agentic-workflow-factory) · 📝 [Essays](https://isaac-maya.github.io/essays/)
"""
    )
