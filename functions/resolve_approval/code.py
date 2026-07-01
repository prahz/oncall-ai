#input_type_name: ResolveInput
#output_type_name: ResolveResult
#function_name: resolve_approval

from typing import Optional
from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod

WORKFLOW = "incident_response"


class ResolveInput(BaseModel):
    incident_id: Optional[str] = None     # incident uuid (preferred)
    incident_number: Optional[int] = None # human INC number, e.g. 1042
    approved: bool                        # True = approve & execute, False = reject
    notes: str = ""                       # optional approver note


class ResolveResult(BaseModel):
    ok: bool
    incident_id: str = ""
    incident_number: int = 0
    run_id: str = ""
    decision: str = ""                    # "approved" | "rejected"
    message: str = ""


def _resolve_incident_id(pod: Pod, data: ResolveInput) -> Optional[str]:
    if data.incident_id:
        return data.incident_id
    if data.incident_number is not None:
        rows = pod.records.list(
            "incidents", limit=5,
            filter=[{"field": "number", "op": "eq", "value": data.incident_number}],
        ).to_dict()["items"]
        if rows:
            return str(rows[0]["id"])
    return None


async def resolve_approval(ctx: FunctionContext, data: ResolveInput) -> ResolveResult:
    pod = Pod.from_env()

    incident_id = _resolve_incident_id(pod, data)
    if not incident_id:
        return ResolveResult(ok=False, message="Could not find that incident. Give an incident id or INC number.")

    # Find the WAITING run for this incident and submit its approval form.
    runs = pod.workflows.runs(WORKFLOW, limit=100).to_dict().get("items", [])
    for r in runs:
        if r.get("status") != "WAITING":
            continue
        run = pod.workflows.run_get(str(r["id"])).to_dict()
        aw = run.get("active_wait") or {}
        if aw.get("wait_type") != "HUMAN":
            continue
        ctx_open = (run.get("execution_context") or {}).get("open") or {}
        if str(ctx_open.get("incident_id")) != str(incident_id):
            continue

        node_id = aw.get("node_id")
        pod.workflows.submit_form(
            str(r["id"]),
            node_id=node_id,
            inputs={"approved": bool(data.approved), "notes": data.notes},
        )
        number = int(ctx_open.get("incident_number") or 0)
        decision = "approved" if data.approved else "rejected"
        verb = "Approved — executing remediation now." if data.approved else "Rejected — escalating to a human."
        return ResolveResult(
            ok=True, incident_id=str(incident_id), incident_number=number,
            run_id=str(r["id"]), decision=decision,
            message=f"INC-{number}: {verb}",
        )

    return ResolveResult(
        ok=False, incident_id=str(incident_id),
        message="No remediation is currently awaiting approval for that incident (already decided or auto-handled).",
    )
