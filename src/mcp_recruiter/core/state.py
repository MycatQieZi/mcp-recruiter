"""Pipeline state machine — lightweight stage transition management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..core.enums import Stage


class PipelineStateMachine:
    """Manages stage transitions in the hiring pipeline.

    Stages: SEA -> SCREEN -> WRITTEN -> INTERVIEW -> COMPLETE
    """

    VALID_TRANSITIONS = {
        Stage.SEA: {Stage.SCREEN, Stage.COMPLETE},  # COMPLETE = failed (no candidates)
        Stage.SCREEN: {Stage.WRITTEN, Stage.COMPLETE},
        Stage.WRITTEN: {Stage.INTERVIEW, Stage.COMPLETE},
        Stage.INTERVIEW: {Stage.COMPLETE},
    }

    def __init__(self, initial_stage: Stage = Stage.SEA):
        self.current_stage = initial_stage
        self.stage_results: dict[Stage, dict] = {}

    def can_transition(self, to_stage: Stage) -> bool:
        return to_stage in self.VALID_TRANSITIONS.get(self.current_stage, set())

    def transition(self, to_stage: Stage) -> Stage:
        if not self.can_transition(to_stage):
            raise ValueError(
                f"Invalid transition: {self.current_stage.value} -> {to_stage.value}"
            )
        self.current_stage = to_stage
        return self.current_stage

    def advance(self) -> Stage:
        """Auto-advance to the next stage based on current stage and results."""
        stage_order = [Stage.SEA, Stage.SCREEN, Stage.WRITTEN, Stage.INTERVIEW, Stage.COMPLETE]
        try:
            idx = stage_order.index(self.current_stage)
            next_stage = stage_order[idx + 1]
            self.transition(next_stage)
            return next_stage
        except (ValueError, IndexError):
            self.transition(Stage.COMPLETE)
            return Stage.COMPLETE

    def set_result(self, stage: Stage, result: dict):
        self.stage_results[stage] = result

    def get_result(self, stage: Stage) -> dict:
        return self.stage_results.get(stage, {})
