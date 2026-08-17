from pathlib import Path

from api.file_utils import (
    SUPPORTED_INPUT_EXTENSIONS,
    filter_supported_files,
    find_supported_session_files,
    is_supported_input_file,
)


def test_supported_extensions_include_batch_parser_document_formats():
    assert {".pdf", ".md", ".doc", ".docx", ".ppt", ".pptx"}.issubset(
        SUPPORTED_INPUT_EXTENSIONS
    )
    assert ".markdown" not in SUPPORTED_INPUT_EXTENSIONS


def test_filter_supported_files_is_case_insensitive():
    files = [
        {"filename": "notes.MD", "path": "/tmp/notes.MD"},
        {"filename": "report.DOCX", "path": "/tmp/report.DOCX"},
        {"filename": "notes.markdown", "path": "/tmp/notes.markdown"},
        {"filename": "archive.zip", "path": "/tmp/archive.zip"},
    ]

    filtered = filter_supported_files(files)

    assert [file_record["filename"] for file_record in filtered] == [
        "notes.MD",
        "report.DOCX",
    ]
    assert is_supported_input_file("presentation.PPTX")


def test_find_supported_session_files_includes_text_and_office_inputs(tmp_path: Path):
    for filename in ["z-notes.md", "a-report.docx", "ignored.zip"]:
        (tmp_path / filename).touch()

    assert [path.name for path in find_supported_session_files(tmp_path)] == [
        "a-report.docx",
        "z-notes.md",
    ]
