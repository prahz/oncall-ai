#input_type_name: SetActionStatusInput
#output_type_name: SetActionStatusResult
#function_name: set_remediation_action_status

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class SetActionStatusInput(BaseModel):
    action_id: str
    status: str
    result: str = ""
    executed_by: str = ""


class SetActionStatusResult(BaseModel):
    action_id: str
    status: str


def set_remediation_action_status(ctx: FunctionContext, data: SetActionStatusInput) -> SetActionStatusResult:
    pod = Pod.from_env()
    fields = {"status": data.status}
    if data.result:
        fields["result"] = data.result
    if data.executed_by:
        fields["executed_by"] = data.executed_by
    pod.table("remediation_actions").update(data.action_id, fields)
    return SetActionStatusResult(action_id=data.action_id, status=data.status)
