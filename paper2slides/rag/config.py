"""
RAG Configuration for Paper2Slides

Manages API, storage, and parser settings for paper processing.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv

from ..utils import get_llm_model

PROJECT_ROOT = Path(__file__).parent.parent

load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=False)

DEFAULT_STORAGE_DIR = PROJECT_ROOT / "rag" / "storage"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "rag" / "output"


@dataclass
class APIConfig:
    """LLM and Embedding API settings.
    
    API key must be provided via environment variable or explicitly.
    Base URL is optional (defaults to OpenAI official API).
    """
    
    llm_api_key: str = field(
        default_factory=lambda: os.getenv("RAG_LLM_API_KEY", "")
    )
    """Required. Set via RAG_LLM_API_KEY env var or pass explicitly."""
    
    llm_base_url: Optional[str] = field(
        default_factory=lambda: os.getenv("RAG_LLM_BASE_URL", None)
    )
    """Optional. If None, uses OpenAI official API. Set via RAG_LLM_BASE_URL env var."""
    
    llm_model: str = field(
        default_factory=lambda: get_llm_model()
    )
    """Chat model name. Resolved via get_llm_model(): LLM_MODEL env wins; when
    RAG_LLM_BASE_URL points off api.openai.com without LLM_MODEL a loud warning
    is logged because the gpt-4o-mini fallback is rejected by most endpoints
    (issue #37)."""
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
    )
    embedding_dim: int = field(
        default_factory=lambda: int(os.getenv("EMBEDDING_DIM", "3072"))
    )
    embedding_max_tokens: int = 8192
    
    def __post_init__(self):
        if not self.llm_api_key:
            raise ValueError(
                "API key is required. Set RAG_LLM_API_KEY environment variable "
                "or pass llm_api_key explicitly."
            )


@dataclass
class StorageConfig:
    """Storage paths for RAG index and parsed outputs."""
    
    storage_dir: str = field(
        default_factory=lambda: str(os.getenv("RAG_STORAGE_DIR", DEFAULT_STORAGE_DIR))
    )
    """Knowledge graph and vector index storage."""
    
    output_dir: str = field(
        default_factory=lambda: str(os.getenv("RAG_OUTPUT_DIR", DEFAULT_OUTPUT_DIR))
    )
    """Parsed paper outputs (markdown, images)."""
    
    def __post_init__(self):
        Path(self.storage_dir).mkdir(parents=True, exist_ok=True)
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)


@dataclass
class ParserConfig:
    """Paper parser settings."""
    
    parser: str = field(default_factory=lambda: os.getenv("PARSER", "mineru"))
    """Parser: 'mineru' or 'docling'."""
    
    parse_method: str = field(default_factory=lambda: os.getenv("PARSE_METHOD", "auto"))
    """Method: 'auto', 'ocr', or 'txt'."""
    
    display_content_stats: bool = field(
        default_factory=lambda: os.getenv("DISPLAY_CONTENT_STATS", "true").lower() == "true"
    )
    """Whether to display content statistics during parsing."""
    
    enable_image_processing: bool = field(
        default_factory=lambda: os.getenv("ENABLE_IMAGE_PROCESSING", "true").lower() == "true"
    )
    enable_table_processing: bool = field(
        default_factory=lambda: os.getenv("ENABLE_TABLE_PROCESSING", "true").lower() == "true"
    )
    enable_equation_processing: bool = field(
        default_factory=lambda: os.getenv("ENABLE_EQUATION_PROCESSING", "true").lower() == "true"
    )


@dataclass
class BatchConfig:
    """Batch processing settings. Aligned with RAGAnythingConfig defaults."""
    
    max_concurrent_files: int = field(
        default_factory=lambda: int(os.getenv("MAX_CONCURRENT_FILES", "1"))
    )
    """Maximum number of files to process concurrently."""
    
    supported_file_extensions: List[str] = field(
        default_factory=lambda: os.getenv(
            "SUPPORTED_FILE_EXTENSIONS",
            ".pdf,.jpg,.jpeg,.png,.bmp,.tiff,.tif,.gif,.webp,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.md"
        ).split(",")
    )
    """List of supported file extensions for batch processing."""
    
    recursive_folder_processing: bool = field(
        default_factory=lambda: os.getenv("RECURSIVE_FOLDER_PROCESSING", "true").lower() == "true"
    )
    """Whether to recursively process subfolders in batch mode."""


@dataclass
class ContextConfig:
    """Context extraction settings. Aligned with RAGAnythingConfig defaults."""
    
    context_window: int = field(
        default_factory=lambda: int(os.getenv("CONTEXT_WINDOW", "1"))
    )
    """Number of pages/chunks to include before and after current item for context."""
    
    context_mode: str = field(
        default_factory=lambda: os.getenv("CONTEXT_MODE", "page")
    )
    """Context extraction mode: 'page' for page-based, 'chunk' for chunk-based."""
    
    max_context_tokens: int = field(
        default_factory=lambda: int(os.getenv("MAX_CONTEXT_TOKENS", "2000"))
    )
    """Maximum number of tokens in extracted context."""
    
    include_headers: bool = field(
        default_factory=lambda: os.getenv("INCLUDE_HEADERS", "true").lower() == "true"
    )
    """Whether to include document headers and titles in context."""
    
    include_captions: bool = field(
        default_factory=lambda: os.getenv("INCLUDE_CAPTIONS", "true").lower() == "true"
    )
    """Whether to include image/table captions in context."""
    
    context_filter_content_types: List[str] = field(
        default_factory=lambda: os.getenv("CONTEXT_FILTER_CONTENT_TYPES", "text").split(",")
    )
    """Content types to include in context extraction."""
    
    content_format: str = field(
        default_factory=lambda: os.getenv("CONTENT_FORMAT", "minerU")
    )
    """Default content format for context extraction."""


@dataclass
class RAGConfig:
    """
    Complete RAG configuration for Paper2Slides.
    All defaults are aligned with RAGAnythingConfig.
    
    Example:
        config = RAGConfig()
        rag = RAGClient(config)
    """
    
    api: APIConfig = field(default_factory=APIConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    parser: ParserConfig = field(default_factory=ParserConfig)
    batch: BatchConfig = field(default_factory=BatchConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    verbose: bool = field(
        default_factory=lambda: os.getenv("VERBOSE", "false").lower() == "true"
    )
    
    @classmethod
    def from_env(cls) -> "RAGConfig":
        """Create from environment variables."""
        return cls()
    
    @classmethod
    def with_paths(
        cls,
        storage_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
        **kwargs
    ) -> "RAGConfig":
        """Create with custom paths."""
        storage = StorageConfig(
            storage_dir=storage_dir or str(DEFAULT_STORAGE_DIR),
            output_dir=output_dir or str(DEFAULT_OUTPUT_DIR),
        )
        return cls(storage=storage, **kwargs)
    
    def to_rag_anything_config(self):
        """Convert to RAGAnythingConfig for internal use."""
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        from raganything import RAGAnythingConfig
        
        return RAGAnythingConfig(
            # Storage
            working_dir=self.storage.storage_dir,
            parser_output_dir=self.storage.output_dir,
            # Parser
            parser=self.parser.parser,
            parse_method=self.parser.parse_method,
            display_content_stats=self.parser.display_content_stats,
            enable_image_processing=self.parser.enable_image_processing,
            enable_table_processing=self.parser.enable_table_processing,
            enable_equation_processing=self.parser.enable_equation_processing,
            # Batch
            max_concurrent_files=self.batch.max_concurrent_files,
            supported_file_extensions=self.batch.supported_file_extensions,
            recursive_folder_processing=self.batch.recursive_folder_processing,
            # Context
            context_window=self.context.context_window,
            context_mode=self.context.context_mode,
            max_context_tokens=self.context.max_context_tokens,
            include_headers=self.context.include_headers,
            include_captions=self.context.include_captions,
            context_filter_content_types=self.context.context_filter_content_types,
            content_format=self.context.content_format,
        )
    
    def __repr__(self) -> str:
        return (
            f"RAGConfig(storage='{self.storage.storage_dir}', "
            f"model='{self.api.llm_model}', parser='{self.parser.parser}')"
        )
