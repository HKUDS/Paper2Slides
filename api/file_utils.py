"""Helpers for identifying files accepted by the API input pipeline."""

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from paper2slides.file_formats import SUPPORTED_FILE_EXTENSIONS

# Keep the API's input contract aligned with the formats used by BatchParser.
SUPPORTED_INPUT_EXTENSIONS = SUPPORTED_FILE_EXTENSIONS


def is_supported_input_file(filename: str) -> bool:
    """Return whether ``filename`` has a format handled by BatchParser."""
    return Path(filename).suffix.lower() in SUPPORTED_INPUT_EXTENSIONS


def filter_supported_files(
    files: Iterable[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Keep uploaded file records that can be passed to the input pipeline."""
    return [
        file_record
        for file_record in files
        if is_supported_input_file(str(file_record.get("filename", "")))
    ]


def find_supported_session_files(session_dir: Path) -> list[Path]:
    """Return supported uploaded files from a session in stable name order."""
    return sorted(
        (
            file_path
            for file_path in session_dir.iterdir()
            if file_path.is_file() and is_supported_input_file(file_path.name)
        ),
        key=lambda file_path: file_path.name.lower(),
    )
