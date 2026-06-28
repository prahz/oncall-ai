#input_type_name: SetIncidentStatusInput
#output_type_name: SetIncidentStatusResult
#function_name: set_incident_status

from datetime import datetime, timezone

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class SetIncidentStatusInput(BaseModel):
    incident_id: str
    status: str
    stamp_mitigated: bool = False
    stamp_resolved: bool = False
    severity: str = ""
    blast_radius: str = ""


class SetIncidentStatusResult(BaseModel):
    incident_id: str
    status: str


def set_incident_status(ctx: FunctionContext, data: SetIncidentStatusInput) -> SetIncidentStatusResult:
    """Reliable verb backing every incidents table_update node. Sets status, optional
    severity/blast_radius, and timestamps mitigated_at/resolved_at when flagged."""
    pod = Pod.from_env()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fields = {"status": data.status}
    if data.severity:
        fields["severity"] = data.severity
    if data.blast_radius:
        fields["blast_radius"] = data.blast_radius
    if data.stamp_mitigated:
        fields["mitigated_at"] = now
    if data.stamp_resolved:
        fields["resolved_at"] = now
    pod.table("incidents").update(data.incident_id, fields)
    return SetIncidentStatusResult(incident_id=data.incident_id, status=data.status)
