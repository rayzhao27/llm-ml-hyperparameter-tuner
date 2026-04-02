# mirrors FileReadTool from Claude Code repo
# src/tools/fileRead.ts — same pattern: validate input, read file, return contents

from pydantic import BaseModel
from pathlib import Path


class ReadToolInput(BaseModel):
    path: str


class ReadToolOutput(BaseModel):
    content: str
    path: str
    lines: int


def read_file(input: ReadToolInput) -> ReadToolOutput:
    path = Path(input.path)

    if not path.exists():
        raise FileNotFoundError(f"file not found: {input.path}")

    if not path.is_file():
        raise ValueError(f"path is not a file: {input.path}")

    content = path.read_text(encoding="utf-8")

    return ReadToolOutput(
        content=content,
        path=str(path.resolve()),
        lines=len(content.splitlines())
    )
