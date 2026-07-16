#input_type_name: FT
#output_type_name: FTR
#function_name: _filetest

from pydantic import BaseModel
from lemma_sdk import FunctionContext, Pod
from io import BytesIO

class FT(BaseModel):
    pass

class FTR(BaseModel):
    note: str

async def _filetest(ctx: FunctionContext, data: FT) -> FTR:
    pod = Pod.from_env()
    tries = []
    for label, fn in (
        ("write_text", lambda: pod.files.write_text("/postmortems/_test.md", "# hello\n")),
        ("upload_file", lambda: pod.files.upload_file(BytesIO(b"# hello\n"), path="/postmortems/_test2.md", filename="_test2.md", directory_path="/postmortems", search_enabled=False)),
    ):
        try:
            fn(); tries.append(f"{label}=OK")
        except Exception as e:
            tries.append(f"{label}=ERR {type(e).__name__}: {e}"[:180])
    return FTR(note=" | ".join(tries))
