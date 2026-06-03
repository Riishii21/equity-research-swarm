"""Lightweight execution tracer.

Records every agent step, tool call, and timing into an ordered log you can
print, inspect, or render in the UI. This is the 'show your work' artifact —
the decision log a reviewer can read to see exactly what the swarm did.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field


@dataclass
class TraceEvent:
    step: str
    detail: str
    elapsed_ms: float


@dataclass
class Tracer:
    events: list[TraceEvent] = field(default_factory=list)
    _t0: float = field(default_factory=time.time)

    def log(self, step: str, detail: str = ""):
        self.events.append(
            TraceEvent(step=step, detail=detail, elapsed_ms=(time.time() - self._t0) * 1000)
        )

    def render(self) -> str:
        lines = ["# Execution trace"]
        for e in self.events:
            lines.append(f"[{e.elapsed_ms:7.1f} ms] {e.step}: {e.detail}")
        return "\n".join(lines)
