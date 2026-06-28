#input_type_name: SetPostMortemStatusInput
#output_type_name: SetPostMortemStatusResult
#function_name: set_post_mortem_status

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod


class SetPostMortemStatusInput(BaseModel):
    post_mortem_id: str
    status: str


class SetPostMortemStatusResult(BaseModel):
    post_mortem_id: str
    status: str


def set_post_mortem_status(ctx: FunctionContext, data: SetPostMortemStatusInput) -> SetPostMortemStatusResult:
    pod = Pod.from_env()
    pod.table("post_mortems").update(data.post_mortem_id, {"status": data.status})
    return SetPostMortemStatusResult(post_mortem_id=data.post_mortem_id, status=data.status)
