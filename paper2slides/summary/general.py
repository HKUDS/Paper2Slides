"""
General document processing
Extract content from RAG results for general documents
"""
from typing import List
from dataclasses import dataclass, field

from .clean import clean_references
from ..rag import RAGQueryResult


@dataclass
class GeneralContent:
    """Extracted general document content."""
    content: str = ""
    raw_rag_results: List[RAGQueryResult] = field(default_factory=list)


EXTRACT_PROMPT = """You are organizing document content. Your task is to restructure the text while preserving ALL details.

CRITICAL RULES:
1. Keep ALL specific numbers, metrics, percentages, scores
2. Keep ALL method names, component names, technical terms
3. Keep ALL examples and case studies with full details

Text to organize:
{content}

Output format:
## DOCUMENT OVERVIEW
[Type and purpose]

## MAIN CONTENT
[Organized content by topics/sections]

### [Topic 1]
[ALL details, numbers, specifics]

### [Topic 2]
[ALL details, numbers, specifics]
...

## KEY DATA & METRICS
[ALL numbers, scores, statistics mentioned]

## SPECIAL ELEMENTS
[Tables, figures, formulas with full descriptions]"""


def merge_answers(
    rag_results: List[RAGQueryResult],
    clean_refs: bool = True,
) -> str:
    """
    Merge all RAG answers from a list of query results.
    
    Args:
        rag_results: List of query results [{"query": ..., "answer": ..., "success": ...}, ...]
        clean_refs: Whether to clean references
    """
    texts = []
    
    for item in rag_results:
        answer = item.get("answer", "")
        if answer and len(answer) > 50:
            if clean_refs:
                answer = clean_references(answer)
            texts.append(answer)
    
    return "\n\n---\n\n".join(texts)


async def extract_general(
    rag_results: List[RAGQueryResult],
    llm_client=None,
    model: str = "gpt-4o-mini",
    clean_refs: bool = True,
    skip_llm: bool = True,
) -> GeneralContent:
    """
    Extract structured content from RAG results for a general document.
    
    Args:
        rag_results: List of query results
        llm_client: OpenAI client (optional if skip_llm=True)
        model: Model to use
        clean_refs: Whether to clean references
        skip_llm: If True, skip LLM extraction and use merged RAG results directly
    
    Note:
        To get original tables/figures, use create_enhanced_summary() from source_extractor
        with remove_tables=False after getting the content.
    """
    merged = merge_answers(rag_results, clean_refs=clean_refs)
    
    if not merged or len(merged) < 100:
        return GeneralContent(raw_rag_results=rag_results)
    
    # Skip LLM: directly use merged RAG results
    if skip_llm:
        return GeneralContent(
            content=merged,
            raw_rag_results=rag_results,
        )
    
    prompt = EXTRACT_PROMPT.format(content=merged)
    
    response = llm_client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=8000,
    )
    
    content = response.choices[0].message.content or ""
    
    return GeneralContent(
        content=content,
        raw_rag_results=rag_results,
    )
