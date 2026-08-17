"""File formats accepted by the document parsing pipeline."""

OFFICE_FORMATS = frozenset({".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"})
IMAGE_FORMATS = frozenset(
    {".png", ".jpeg", ".jpg", ".bmp", ".tiff", ".tif", ".gif", ".webp"}
)
TEXT_FORMATS = frozenset({".txt", ".md"})

SUPPORTED_FILE_EXTENSIONS = frozenset(
    {".pdf"} | OFFICE_FORMATS | IMAGE_FORMATS | TEXT_FORMATS
)
