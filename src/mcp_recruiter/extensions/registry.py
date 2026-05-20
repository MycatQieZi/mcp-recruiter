"""Extension registry — discover and manage candidate type handlers."""

from __future__ import annotations

from ..core.enums import CandidateType
from .base import CandidateTypeHandler
from .mcp_tool import MCPToolHandler


class ExtensionRegistry:
    """Registry of candidate type handlers. Plugins can register via entry points."""

    def __init__(self):
        self._handlers: dict[CandidateType, CandidateTypeHandler] = {}
        self._register_defaults()

    def _register_defaults(self):
        mcp = MCPToolHandler()
        self._handlers[mcp.candidate_type] = mcp

    def register(self, handler: CandidateTypeHandler):
        self._handlers[handler.candidate_type] = handler

    def get(self, ctype: CandidateType) -> CandidateTypeHandler | None:
        return self._handlers.get(ctype)

    @property
    def supported_types(self) -> list[CandidateType]:
        return list(self._handlers.keys())
