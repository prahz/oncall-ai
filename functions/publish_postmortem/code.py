#input_type_name: PublishInput
#output_type_name: PublishResult
#function_name: publish_postmortem

# Deterministically publish an incident's post-mortem markdown to a real file
# under /postmortems, so it shows up in the pod's docs. The postmortem_writer
# agent produces the markdown (incidents.postmortem_md); this function turns it
# into /postmortems/INC-<number>.md and records the path on the incident.

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class PublishInput(BaseModel):
    incident_id: str


class PublishResult(BaseModel):
    incident_id: str
    postmortem_path: str = ""
    written: bool = False
    detail: str = ""


async def publish_postmortem(ctx: FunctionContext, data: PublishInput) -> PublishResult:
    pod = Pod.from_env()
    inc = pod.table("incidents").get(data.incident_id)
    number = inc.get("number") or "unknown"
    md = inc.get("postmortem_md") or ""
    path = f"/postmortems/INC-{number}.md"

    if not md:
        return PublishResult(incident_id=data.incident_id, detail="no postmortem_md to publish")

    try:
        pod.files.write_text(path, md)
    except Exception as exc:
        # Non-fatal: the markdown still lives on the incident and renders in the
        # dashboard. Record the failure but don't break the workflow.
        return PublishResult(incident_id=data.incident_id, detail=f"file write failed: {exc}"[:180])

    pod.table("incidents").update(data.incident_id, {"postmortem_path": path})
    return PublishResult(incident_id=data.incident_id, postmortem_path=path, written=True,
                         detail="published")
