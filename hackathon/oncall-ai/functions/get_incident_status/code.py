#input_type_name: GetIncidentStatusInput
#output_type_name: GetIncidentStatusResult
#function_name: get_incident_status

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class GetIncidentStatusInput(BaseModel):
    incident_id: str


class GetIncidentStatusResult(BaseModel):
    status: str
    exists: bool


def get_incident_status(ctx: FunctionContext, data: GetIncidentStatusInput) -> GetIncidentStatusResult:
    pod = Pod.from_env()
    try:
        row = pod.table("incidents").get(data.incident_id)
    except Exception:
        return GetIncidentStatusResult(status="", exists=False)
    return GetIncidentStatusResult(status=str(row.get("status") or ""), exists=True)
