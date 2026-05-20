from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID


class PipelineStore:
    """JSON-file-based persistence for pipeline state.

    For prototype simplicity, uses structured JSON files.
    Can be swapped for SQLite via sqlite-utils in the future.
    """

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._jobs_dir = self.data_dir / "jobs"
        self._jobs_dir.mkdir(exist_ok=True)

    # ── Job CRUD ──────────────────────────────────────

    def save_job(self, job: dict) -> None:
        self._write_json(self._job_path(job["id"]), job)

    def load_job(self, job_id: UUID) -> dict | None:
        return self._read_json(self._job_path(job_id))

    def list_jobs(self) -> list[dict]:
        results = []
        for f in sorted(self._jobs_dir.glob("*.json")):
            data = self._read_json(f)
            if data:
                results.append(data)
        return results

    # ── Candidates ────────────────────────────────────

    def save_candidates(self, candidates: list[dict]) -> None:
        self._write_json(self.data_dir / "candidates.json", candidates)

    def load_candidates(self) -> list[dict]:
        return self._read_json(self.data_dir / "candidates.json") or []

    # ── Resumes ───────────────────────────────────────

    def save_resumes(self, resumes: list[dict]) -> None:
        self._write_json(self.data_dir / "resumes.json", resumes)

    def load_resumes(self) -> list[dict]:
        return self._read_json(self.data_dir / "resumes.json") or []

    # ── ScoreCards ────────────────────────────────────

    def save_score_cards(self, cards: list[dict]) -> None:
        self._write_json(self.data_dir / "score_cards.json", cards)

    def load_score_cards(self) -> list[dict]:
        return self._read_json(self.data_dir / "score_cards.json") or []

    # ── Test Results ──────────────────────────────────

    def save_test_results(self, results: list[dict]) -> None:
        self._write_json(self.data_dir / "test_results.json", results)

    def load_test_results(self) -> list[dict]:
        return self._read_json(self.data_dir / "test_results.json") or []

    # ── Report ────────────────────────────────────────

    def save_report(self, report: dict) -> None:
        reports_dir = self.data_dir / "reports"
        reports_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._write_json(reports_dir / f"report_{ts}.json", report)

    # ── Helpers ───────────────────────────────────────

    def _job_path(self, job_id: UUID) -> Path:
        return self._jobs_dir / f"{job_id}.json"

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _read_json(path: Path) -> dict | None:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
