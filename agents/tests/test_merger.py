"""Tests for the merger node — deduplication, sorting, and capping logic."""

from __future__ import annotations


from agents.merger import merger_node, compute_similarity, deduplicate_findings
from shared.schemas.finding import FindingCreate


class TestMessageSimilarity:
    """Tests for message similarity computation."""

    def test_identical_messages(self):
        assert compute_similarity("hello world", "hello world") == 1.0

    def test_completely_different_messages(self):
        assert compute_similarity("foo", "barbaz") < 0.5

    def test_similar_messages(self):
        sim = compute_similarity(
            "Unused import: os",
            "Unused import: os module"
        )
        assert sim >= 0.7

    def test_empty_messages(self):
        assert compute_similarity("", "") == 0.0
        assert compute_similarity("hello", "") == 0.0


class TestDeduplication:
    """Tests for finding deduplication."""

    def test_removes_exact_duplicates_same_line(self):
        findings = [
            FindingCreate(file_path="a.py", line_number=10, severity="warning",
             message="Unused import os", agent="static"),
            FindingCreate(file_path="a.py", line_number=10, severity="error",
             message="Unused import os", agent="style"),
        ]
        result = deduplicate_findings(findings)
        # Should keep only one, preferring the higher severity (error)
        assert len(result) == 1
        assert result[0].severity == "error"

    def test_keeps_different_files(self):
        findings = [
            FindingCreate(file_path="a.py", line_number=10, severity="warning",
             message="Unused import", agent="static"),
            FindingCreate(file_path="b.py", line_number=10, severity="warning",
             message="Unused import", agent="static"),
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 2

    def test_keeps_different_lines(self):
        findings = [
            FindingCreate(file_path="a.py", line_number=10, severity="warning",
             message="Unused import", agent="static"),
            FindingCreate(file_path="a.py", line_number=20, severity="warning",
             message="Unused import", agent="static"),
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 2

    def test_null_line_numbers_not_deduplicated(self):
        findings = [
            FindingCreate(file_path="a.py", line_number=None, severity="info",
             message="General issue", agent="arch"),
            FindingCreate(file_path="a.py", line_number=None, severity="info",
             message="General issue", agent="style"),
        ]
        result = deduplicate_findings(findings)
        # line_number=None should not be deduplicated
        assert len(result) == 2


class TestMergerNode:
    """Tests for the merge_findings_node."""

    def test_combines_all_agents(self):
        state = {
            "static_findings": [
                FindingCreate(agent="static", file_path="a.py", line_number=1,
                 severity="warning", message="msg1")
            ],
            "security_findings": [
                FindingCreate(agent="security", file_path="b.py", line_number=2,
                 severity="error", message="msg2")
            ],
            "style_findings": [
                FindingCreate(agent="style", file_path="c.py", line_number=3,
                 severity="suggestion", message="msg3")
            ],
            "arch_findings": [
                FindingCreate(agent="architecture", file_path="d.py", line_number=4,
                 severity="info", message="msg4")
            ],
        }
        result = merger_node(state)
        assert len(result["merged_findings"]) == 4

    def test_sorts_by_severity(self):
        state = {
            "static_findings": [
                FindingCreate(agent="static", file_path="a.py", line_number=1,
                 severity="suggestion", message="low"),
            ],
            "security_findings": [
                FindingCreate(agent="security", file_path="b.py", line_number=2,
                 severity="error", message="high"),
            ],
            "style_findings": [],
            "arch_findings": [
                FindingCreate(agent="arch", file_path="c.py", line_number=3,
                 severity="warning", message="medium"),
            ],
        }
        result = merger_node(state)
        severities = [f.severity.value for f in result["merged_findings"]]
        assert severities == ["error", "warning", "suggestion"]

    def test_caps_at_50(self):
        state = {
            "static_findings": [
                FindingCreate(agent="static", file_path=f"file_{i}.py",
                 line_number=i, severity="info", message=f"msg {i}")
                for i in range(30)
            ],
            "security_findings": [
                FindingCreate(agent="security", file_path=f"sec_{i}.py",
                 line_number=i, severity="warning", message=f"sec {i}")
                for i in range(30)
            ],
            "style_findings": [],
            "arch_findings": [],
        }
        result = merger_node(state)
        assert len(result["merged_findings"]) <= 50

    def test_handles_empty_state(self):
        state = {
            "static_findings": [],
            "security_findings": [],
            "style_findings": [],
            "arch_findings": [],
        }
        result = merger_node(state)
        assert result["merged_findings"] == []
