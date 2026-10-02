"""
Summary Stage - Content extraction from RAG results
"""
import os
import logging
from pathlib import Path
from typing import Dict

from ...utils import load_json, save_json, save_text, get_llm_model
from ..paths import get_rag_checkpoint, get_summary_checkpoint, get_summary_md

logger = logging.getLogger(__name__)


async def run_summary_stage(base_dir: Path, config: Dict) -> Dict:
    """Stage 2: Extract content from RAG results."""
    from openai import OpenAI
    from paper2slides.summary import extract_paper, extract_general, extract_tables_and_figures, OriginalElements
    from paper2slides.summary.paper import extract_paper_metadata_from_markdown
    
    rag_data = load_json(get_rag_checkpoint(base_dir, config))
    if not rag_data:
        raise ValueError("Missing RAG checkpoint.")
    
    rag_results = rag_data["rag_results"]
    markdown_paths = rag_data.get("markdown_paths", [])
    content_type = rag_data.get("content_type", "paper")
    
    api_key = os.getenv("RAG_LLM_API_KEY", "")
    base_url = os.getenv("RAG_LLM_BASE_URL")
    model = get_llm_model()
    llm_client = OpenAI(api_key=api_key, base_url=base_url)
    
    logger.info(f"Extracting content from indexed documents ({content_type})...")
    
    if content_type == "paper":
        # Extract paper metadata directly from markdown (bypasses RAG)
        if markdown_paths:
            num_files = len(markdown_paths)
            logger.info(f"  Extracting paper metadata from {num_files} markdown file(s)...")
            
            paper_metadata = await extract_paper_metadata_from_markdown(
                markdown_paths=markdown_paths,
                llm_client=llm_client,
                model=model,
                max_chars_per_file=3000
            )
            
            # Replace paper_info in RAG results with direct extraction
            metadata_result = {
                "query": "List the paper title, author names and their institutional affiliations.",
                "answer": paper_metadata,
                "mode": "direct_markdown_extraction",
                "success": True,
            }
            rag_results["paper_info"] = [metadata_result]
            logger.info("  Paper metadata extracted successfully")
        
        content = await extract_paper(
            rag_results=rag_results,
            llm_client=llm_client,
            model=model,
            parallel=True,
            max_concurrency=5,
        )
        summary_text = content.to_summary()
    else:
        all_results = []
        for items in rag_results.values():
            all_results.extend(items)
        content = await extract_general(
            rag_results=all_results,
            llm_client=llm_client,
            model=model,
        )
        summary_text = content.content
    
    logger.info(f"  Summary: {len(summary_text)} chars")
    
    logger.info("Extracting tables and figures...")
    # Extract from all markdown files (single or multiple)
    all_tables = []
    all_figures = []
    base_path = ""
    
    for i, md_path in enumerate(markdown_paths):
        origin = extract_tables_and_figures(md_path)
        
        # Add document prefix to IDs if multiple documents (to avoid conflicts)
        if len(markdown_paths) > 1:
            doc_prefix = f"Doc{i+1}"
            # Prefix table IDs
            for table in origin.tables:
                if not table.table_id.startswith(doc_prefix):
                    table.table_id = f"{doc_prefix}_{table.table_id}"
            # Prefix figure IDs
            for figure in origin.figures:
                if not figure.figure_id.startswith(doc_prefix):
                    figure.figure_id = f"{doc_prefix}_{figure.figure_id}"
        
        all_tables.extend(origin.tables)
        all_figures.extend(origin.figures)
        if not base_path and origin.base_path:
            base_path = origin.base_path
    
    origin = OriginalElements(
        tables=all_tables,
        figures=all_figures,
        base_path=base_path
    )
    
    logger.info(f"  Tables: {len(all_tables)}, Figures: {len(all_figures)}")
    
    # Save to mode-specific directory
    save_text(get_summary_md(base_dir, config), summary_text)
    
    result = {
        "content_type": content_type,
        "content": content.__dict__,
        "origin": {
            "tables": origin.get_table_info(),
            "figures": origin.get_figure_info(),
            "base_path": origin.base_path,
        },
        "markdown_paths": markdown_paths,  # All markdown files
    }
    
    checkpoint_path = get_summary_checkpoint(base_dir, config)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    
    save_json(checkpoint_path, result)
    logger.info(f"  Saved: {checkpoint_path}")
    return result

