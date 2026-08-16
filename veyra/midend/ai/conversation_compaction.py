"""Structured conversation history compaction for VEYRA MIDEND.

Preserves recent conversation turns verbatim while condensing older context
into an authoritative structured session state summary with verifiable
execution and input references.
"""

from __future__ import annotations

import re
from typing import Any


class ConversationCompactor:
    def __init__(self, max_recent_turns: int = 4):
        self.max_recent_turns = max_recent_turns

    def compact_history(
        self,
        messages: list[dict[str, Any]],
        session_metadata: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        """Compact conversation messages into structured session summary + recent turns."""
        if not messages:
            return []

        # Number of raw messages to keep verbatim (e.g. 4 turns = 8 messages)
        keep_count = self.max_recent_turns * 2
        if len(messages) <= keep_count:
            return [{"role": m["role"], "content": m["content"]} for m in messages if m.get("content")]

        older_messages = messages[:-keep_count]
        recent_messages = messages[-keep_count:]

        # Extract structured state from older messages and metadata
        summary_lines = ["[SESSION STATE SUMMARY — Authoritative Context]"]

        meta = session_metadata or {}
        if meta.get("analysis_input_id"):
            summary_lines.append(f"- Active Analysis Input: {meta['analysis_input_id']} ({meta.get('analysis_filename', 'file')})")
        if meta.get("calibration_input_id"):
            summary_lines.append(f"- Active Calibration Dataset: {meta['calibration_input_id']}")
        if meta.get("active_skill"):
            summary_lines.append(f"- Active Skill: {meta['active_skill']}")

        # Scan older messages for protospacers, execution references, or key findings
        extracted_exec_ids = set()
        extracted_protospacers = set()

        for msg in older_messages:
            content = msg.get("content") or ""
            # Find execution IDs
            for match in re.findall(r"exec_[a-zA-Z0-9_]+", content):
                extracted_exec_ids.add(match)
            # Find 20nt protospacer DNA sequences
            for match in re.findall(r"\b[ACGTN]{20,23}\b", content):
                if len(match) in {20, 23}:
                    extracted_protospacers.add(match)

        if extracted_exec_ids:
            summary_lines.append(f"- Verified Prior Execution IDs: {', '.join(sorted(extracted_exec_ids)[:5])}")
        if extracted_protospacers:
            summary_lines.append(f"- Identified Target Candidates: {', '.join(sorted(extracted_protospacers)[:4])}")

        # Add brief turn synopsis
        user_queries = [m["content"][:80] for m in older_messages if m.get("role") == "user" and m.get("content")]
        if user_queries:
            summary_lines.append(f"- Prior Topics Covered: {'; '.join(user_queries[:3])}")

        summary_text = "\n".join(summary_lines)

        compacted = [{"role": "system", "content": summary_text}]
        for m in recent_messages:
            if m.get("content"):
                compacted.append({"role": m["role"], "content": m["content"]})

        return compacted
