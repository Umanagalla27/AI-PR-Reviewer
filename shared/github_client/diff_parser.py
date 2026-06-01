"""
Unified diff parser for GitHub PR diffs.

Parses the unified diff format into structured FileHunk objects
that can be passed to AI agents for review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class FileHunk:
    """Represents a single hunk within a file diff."""

    file_path: str
    old_start: int
    new_start: int
    old_lines: int
    new_lines: int
    content: str
    added_lines: list[int] = field(default_factory=list)
    removed_lines: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "file_path": self.file_path,
            "old_start": self.old_start,
            "new_start": self.new_start,
            "old_lines": self.old_lines,
            "new_lines": self.new_lines,
            "content": self.content,
            "added_lines": self.added_lines,
            "removed_lines": self.removed_lines,
        }


# Matches diff header: diff --git a/path/to/file b/path/to/file
DIFF_HEADER_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$")

# Matches hunk header: @@ -old_start,old_lines +new_start,new_lines @@
HUNK_HEADER_RE = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$"
)


def parse_unified_diff(diff_text: str) -> list[FileHunk]:
    """
    Parse a unified diff string into a list of FileHunk objects.

    Handles:
      - Multiple files in a single diff
      - Multiple hunks per file
      - Binary files (skipped)
      - Rename/copy operations
      - No-newline-at-end-of-file markers

    Args:
        diff_text: The raw unified diff text from GitHub API.

    Returns:
        A list of FileHunk objects, one per hunk per file.
    """
    if not diff_text or not diff_text.strip():
        return []

    hunks: list[FileHunk] = []
    lines = diff_text.split("\n")
    current_file: str | None = None
    i = 0

    while i < len(lines):
        line = lines[i]

        # Match diff header to get the file path
        header_match = DIFF_HEADER_RE.match(line)
        if header_match:
            current_file = header_match.group(2)
            # Skip to next line (could be index, mode, or --- line)
            i += 1
            continue

        # Match hunk header
        hunk_match = HUNK_HEADER_RE.match(line)
        if hunk_match and current_file:
            old_start = int(hunk_match.group(1))
            old_lines = int(hunk_match.group(2)) if hunk_match.group(2) else 1
            new_start = int(hunk_match.group(3))
            new_lines = int(hunk_match.group(4)) if hunk_match.group(4) else 1

            # Collect hunk content
            hunk_content_lines: list[str] = [line]  # Include header
            added: list[int] = []
            removed: list[int] = []

            current_new_line = new_start
            current_old_line = old_start
            i += 1

            while i < len(lines):
                hunk_line = lines[i]

                # Stop at next diff or hunk header
                if DIFF_HEADER_RE.match(hunk_line) or HUNK_HEADER_RE.match(hunk_line):
                    break

                # Skip no-newline marker
                if hunk_line.startswith("\\ No newline"):
                    hunk_content_lines.append(hunk_line)
                    i += 1
                    continue

                if hunk_line.startswith("+"):
                    added.append(current_new_line)
                    current_new_line += 1
                    hunk_content_lines.append(hunk_line)
                elif hunk_line.startswith("-"):
                    removed.append(current_old_line)
                    current_old_line += 1
                    hunk_content_lines.append(hunk_line)
                elif hunk_line.startswith(" ") or hunk_line == "":
                    current_new_line += 1
                    current_old_line += 1
                    hunk_content_lines.append(hunk_line)
                else:
                    # Unknown line format, might be end of diff section
                    hunk_content_lines.append(hunk_line)

                i += 1

            hunks.append(
                FileHunk(
                    file_path=current_file,
                    old_start=old_start,
                    new_start=new_start,
                    old_lines=old_lines,
                    new_lines=new_lines,
                    content="\n".join(hunk_content_lines),
                    added_lines=added,
                    removed_lines=removed,
                )
            )
            continue

        i += 1

    return hunks
