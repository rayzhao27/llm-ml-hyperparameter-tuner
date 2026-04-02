# mirrors BashTool from Claude Code repo
# src/tools/bash.ts — run a command, stream output line by line, return result

import subprocess
from pydantic import BaseModel


class ExecuteToolInput(BaseModel):
    command: str
    cwd: str
    timeout_seconds: int = 600  # 10 min max per smoke test


class ExecuteToolOutput(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    success: bool


def execute_command(
        input: ExecuteToolInput,
        on_output=None  # callback for live streaming — mirrors BashTool's stream behavior
) -> ExecuteToolOutput:

    process = subprocess.Popen(
        input.command,
        shell=True,
        cwd=input.cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # merge stderr into stdout so logs stream in order
        text=True,
        bufsize=1  # line buffered
    )

    stdout_lines = []

    # stream output line by line
    for line in process.stdout:
        stdout_lines.append(line)
        if on_output:
            on_output(line)  # send to WebSocket in real time

    process.wait(timeout=input.timeout_seconds)

    full_output = "".join(stdout_lines)

    return ExecuteToolOutput(
        stdout=full_output.strip(),
        stderr="",
        exit_code=process.returncode,
        success=process.returncode == 0
    )