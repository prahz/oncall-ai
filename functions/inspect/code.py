#input_type_name: InspectInput
#output_type_name: InspectOutput
#function_name: inspect

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod
import pydoc
from lemma_sdk.resources.conversations import CreateConversationRequest

class InspectInput(BaseModel):
    pass

class InspectOutput(BaseModel):
    result: str

async def inspect(ctx: FunctionContext, data: InspectInput) -> InspectOutput:
    pod = Pod.from_env()
    try:
        doc1 = pydoc.render_doc(CreateConversationRequest, renderer=pydoc.plaintext)
        # also let's just inspect the fields of CreateConversationRequest
        fields = CreateConversationRequest.model_fields.keys()
        return InspectOutput(result=str(list(fields)))
    except Exception as e:
        return InspectOutput(result=str(e))
