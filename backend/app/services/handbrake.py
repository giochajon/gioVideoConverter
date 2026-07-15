import asyncio
import re
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

_PROGRESS_RE = re.compile(r"Encoding:.*?(\d+(?:\.\d+)?)\s*%")


@dataclass
class HandbrakeResult:
    exit_code: int
    stderr_tail: str


async def list_presets() -> list[str]:
    proc = await asyncio.create_subprocess_exec(
        "HandBrakeCLI", "--preset-list",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    presets: list[str] = []
    for line in stdout.decode(errors="ignore").splitlines():
        # Category headers (e.g. "General/") have no indent; descriptions are
        # indented 8+ spaces. Preset names are the 4-space-indented lines.
        if line.startswith("        ") or not line.startswith("    "):
            continue
        name = line.strip()
        if name:
            presets.append(name)
    return presets or ["Fast 720p30"]


@dataclass
class Transcode:
    """Wraps a single HandBrakeCLI run so its subprocess can be tracked/killed
    externally while progress is streamed to the caller."""

    source_path: str
    dest_path: str
    preset: str
    proc: Optional[asyncio.subprocess.Process] = field(default=None, init=False)
    result: Optional[HandbrakeResult] = field(default=None, init=False)

    async def run(self) -> AsyncIterator[float]:
        self.proc = await asyncio.create_subprocess_exec(
            "HandBrakeCLI",
            "-i", self.source_path,
            "-o", self.dest_path,
            "--preset", self.preset,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert self.proc.stdout is not None
        tail: list[str] = []
        buffer = b""

        def _take_lines() -> list[str]:
            nonlocal buffer
            lines = []
            while True:
                idx = min((i for i in (buffer.find(b"\n"), buffer.find(b"\r")) if i != -1), default=-1)
                if idx == -1:
                    break
                lines.append(buffer[:idx].decode(errors="ignore"))
                buffer = buffer[idx + 1:]
            return lines

        while True:
            chunk = await self.proc.stdout.read(4096)
            if not chunk:
                break
            buffer += chunk
            for text in _take_lines():
                tail.append(text)
                del tail[:-20]
                m = _PROGRESS_RE.search(text)
                if m:
                    yield float(m.group(1))

        if buffer:
            text = buffer.decode(errors="ignore")
            tail.append(text)
            m = _PROGRESS_RE.search(text)
            if m:
                yield float(m.group(1))

        exit_code = await self.proc.wait()
        self.result = HandbrakeResult(exit_code=exit_code, stderr_tail="".join(tail))

    def kill(self) -> None:
        if self.proc and self.proc.returncode is None:
            self.proc.kill()
