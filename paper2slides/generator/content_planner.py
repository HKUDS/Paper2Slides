"""
Content Planner
"""
import json
import base64
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from openai import OpenAI

from .config import GenerationInput, OutputType
from ..summary import FigureInfo, TableInfo
from ..prompts.content_planning import (
    PAPER_SLIDES_PLANNING_PROMPT,
    PAPER_POSTER_PLANNING_PROMPT,
    PAPER_POSTER_DENSITY_GUIDELINES,
    GENERAL_SLIDES_PLANNING_PROMPT,
    GENERAL_POSTER_PLANNING_PROMPT,
    GENERAL_POSTER_DENSITY_GUIDELINES,
)


@dataclass
class TableRef:
    """Table reference for a section."""
    table_id: str           # e.g., "Table 1"
    extract: str = ""       # Optional: which part to show, html content
    focus: str = ""         # Optional: what aspect to emphasize


@dataclass
class FigureRef:
    """Figure reference for a section."""
    figure_id: str          # e.g., "Figure 1"
    focus: str = ""         # Optional: what to emphasize, description of the figure


@dataclass
class Section:
    """A single section/slide in the output."""
    id: str
    title: str
    section_type: str  
    content: str
    tables: List[TableRef] = field(default_factory=list)
    figures: List[FigureRef] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "title": self.title,
            "type": self.section_type,
            "content": self.content,
        }
        
        # Tables with optional extract/focus
        result["tables"] = []
        for t in self.tables:
            t_dict = {"table_id": t.table_id}
            if t.extract:
                t_dict["extract"] = t.extract
            if t.focus:
                t_dict["focus"] = t.focus
            result["tables"].append(t_dict)
        
        # Figures with optional focus
        result["figures"] = []
        for f in self.figures:
            f_dict = {"figure_id": f.figure_id}
            if f.focus:
                f_dict["focus"] = f.focus
            result["figures"].append(f_dict)
        
        return result


@dataclass
class ContentPlan:
    """Planned content structure for generation."""
    output_type: str
    sections: List[Section] = field(default_factory=list)
    tables_index: Dict[str, TableInfo] = field(default_factory=dict)
    figures_index: Dict[str, FigureInfo] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_section_tables(self, section: Section) -> List[tuple]:
        """Get (TableInfo, extract) pairs for a section."""
        result = []
        for ref in section.tables:
            if ref.table_id in self.tables_index:
                result.append((self.tables_index[ref.table_id], ref.extract))
        return result
    
    def get_section_figures(self, section: Section) -> List[tuple]:
        """Get (FigureInfo, focus) pairs for a section."""
        result = []
        for ref in section.figures:
            if ref.figure_id in self.figures_index:
                result.append((self.figures_index[ref.figure_id], ref.focus))
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "output_type": self.output_type,
            "sections": [s.to_dict() for s in self.sections],
            "metadata": self.metadata,
        }


class ContentPlanner:
    """Plans content structure using multimodal LLM."""
    
    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        model: Optional[str] = None,
        max_tokens: int = None,
    ):
        import os
        self.api_key = api_key or os.getenv("RAG_LLM_API_KEY", "")
        self.base_url = base_url or os.getenv("RAG_LLM_BASE_URL")
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o")
        # max_tokens: default 16000, override via RAG_LLM_MAX_TOKENS env or constructor
        # Note: deepseek has 8192 limit, set RAG_LLM_MAX_TOKENS=8192 if using deepseek
        self.max_tokens = max_tokens or int(os.getenv("RAG_LLM_MAX_TOKENS", "16000"))
        
        kwargs = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self.client = OpenAI(**kwargs)
    
    def plan(self, gen_input: GenerationInput) -> ContentPlan:
        """Create a content plan from generation input."""
        # Build tables index
        tables_index = {}
        for tbl in gen_input.origin.tables:
            tables_index[tbl.table_id] = tbl
        
        # Build figures index
        figures_index = {}
        for fig in gen_input.origin.figures:
            figures_index[fig.figure_id] = fig
        
        # Get summary and format tables/figures
        summary = gen_input.get_summary_text()
        tables_md = gen_input.origin.get_tables_markdown()
        figure_images = self._load_figure_images(gen_input.origin)
        
        # Plan based on output type
        if gen_input.config.output_type == OutputType.POSTER:
            sections = self._plan_poster(gen_input, summary, tables_md, figure_images)
        else:
            sections = self._plan_slides(gen_input, summary, tables_md, figure_images)
        
        return ContentPlan(
            output_type=gen_input.config.output_type.value,
            sections=sections,
            tables_index=tables_index,
            figures_index=figures_index,
            metadata={
                "density": gen_input.config.poster_density.value 
                          if gen_input.config.output_type == OutputType.POSTER else None,
                "page_range": gen_input.config.get_page_range()
                             if gen_input.config.output_type == OutputType.SLIDES else None,
            },
        )
    
    def _plan_slides(
        self,
        gen_input: GenerationInput,
        summary: str,
        tables_md: str,
        figure_images: List[Dict],
    ) -> List[Section]:
        """Plan slides sections."""
        min_pages, max_pages = gen_input.config.get_page_range()
        
        # Select prompt template based on content type
        template = PAPER_SLIDES_PLANNING_PROMPT if gen_input.is_paper() else GENERAL_SLIDES_PLANNING_PROMPT
        
        # Build assets section based on available tables/figures
        assets_section = self._build_assets_section(tables_md, bool(figure_images))
        
        prompt = template.format(
            min_pages=min_pages,
            max_pages=max_pages,
            summary=self._truncate(summary, 10000),
            assets_section=assets_section,
        )
        
        result = self._call_multimodal_llm(prompt, figure_images)
        return self._parse_sections(result, is_slides=True)
    
    def _plan_poster(
        self,
        gen_input: GenerationInput,
        summary: str,
        tables_md: str,
        figure_images: List[Dict],
    ) -> List[Section]:
        """Plan poster sections."""
        density = gen_input.config.poster_density.value
        
        # Select density guidelines and prompt template based on content type
        if gen_input.is_paper():
            guidelines_map = PAPER_POSTER_DENSITY_GUIDELINES
            template = PAPER_POSTER_PLANNING_PROMPT
        else:
            guidelines_map = GENERAL_POSTER_DENSITY_GUIDELINES
            template = GENERAL_POSTER_PLANNING_PROMPT
        
        density_guidelines = guidelines_map.get(density, guidelines_map["medium"])
        
        # Build assets section based on available tables/figures
        assets_section = self._build_assets_section(tables_md, bool(figure_images))
        
        prompt = template.format(
            density_guidelines=density_guidelines,
            summary=self._truncate(summary, 10000),
            assets_section=assets_section,
        )
        
        result = self._call_multimodal_llm(prompt, figure_images)
        return self._parse_sections(result, is_slides=False)
    
    def _build_assets_section(self, tables_md: str, has_figures: bool) -> str:
        """Build the tables/figures section based on available assets."""
        has_tables = bool(tables_md)
        
        if not has_tables and not has_figures:
            return ""
        
        parts = ["\n## Original Tables and Figures"]
        
        if has_tables and has_figures:
            parts.append("Below are the original tables and figures. Tables contain precise data, figures illustrate concepts visually. Use them to supplement the content.")
        elif has_tables:
            parts.append("Below are the original tables containing precise data. Use them to supplement the content.")
        else:
            parts.append("Below are the original figures illustrating concepts visually. Use them to supplement the content.")
        
        if has_tables:
            parts.append(f"\n{tables_md}")
        
        if has_figures:
            parts.append("\n[FIGURE_IMAGES]")
        
        parts.append("")  # Trailing newline
        return "\n".join(parts)
    
    def _call_multimodal_llm(self, text_prompt: str, figure_images: List[Dict]) -> str:
        """Call multimodal LLM with text and images inline."""
        import logging
        logger = logging.getLogger(__name__)
        
        MARKER = "[FIGURE_IMAGES]"
        content = []
        
        if MARKER in text_prompt and figure_images:
            # Split prompt and insert images at marker position
            before, after = text_prompt.split(MARKER, 1)
            
            if before.strip():
                content.append({"type": "text", "text": before})
            
            # Insert caption + image for each figure
            for fig in figure_images:
                # Caption text
                if fig['caption']:
                    caption_text = f"**{fig['figure_id']}**: {fig['caption']}"
                else:
                    caption_text = f"**{fig['figure_id']}**"
                content.append({"type": "text", "text": caption_text})
                
                # Base64 image
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{fig['mime_type']};base64,{fig['base64']}",
                        # "detail": "auto",
                    }
                })
            
            if after.strip():
                content.append({"type": "text", "text": after})
            logger.info(f"Calling LLM with {len(figure_images)} images")
        else:
            # No marker or no images: text only
            content.append({"type": "text", "text": text_prompt})
            logger.info("Calling LLM with text only (no images)")
        
        try:
            logger.info(f"Calling {self.model} with max_tokens={self.max_tokens}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": content}],
                max_tokens=self.max_tokens,
            )
            result = response.choices[0].message.content or ""
            logger.info(f"LLM returned {len(result)} characters")
            return result
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            logger.error(f"Model: {self.model}, Content items: {len(content)}")
            raise
    
    def _parse_sections(self, llm_response: str, is_slides: bool = True) -> List[Section]:
        """Parse LLM response into Section objects.
        
        Args:
            llm_response: The LLM response containing JSON
            is_slides: If True, auto-determine section_type based on position (opening/content/ending).
                       If False (poster), all sections are "content".
        """
        # Debug: Log the raw LLM response
        import logging
        logger = logging.getLogger(__name__)
        logger.info("=" * 80)
        logger.info("LLM Response for Content Planning:")
        logger.info("-" * 80)
        logger.info(llm_response[:2000])  # Log first 2000 chars
        if len(llm_response) > 2000:
            logger.info(f"... (truncated, total length: {len(llm_response)} chars)")
        logger.info("=" * 80)
        
        # Extract JSON
        json_match = re.search(r'```json\s*(.*?)\s*```', llm_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            logger.info("Found JSON in code block")
        else:
            logger.warning("No JSON code block found, trying to extract raw JSON")
            json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
            json_str = json_match.group(0) if json_match else "{}"
            if not json_match:
                logger.error("No JSON found in LLM response at all!")
        
        # Clean up invalid escape sequences before parsing
        # Replace invalid escape sequences with safe versions
        def fix_invalid_escapes(s):
            """Fix common invalid escape sequences in JSON strings."""
            # Find all escape sequences
            result = []
            i = 0
            while i < len(s):
                if s[i] == '\\' and i + 1 < len(s):
                    next_char = s[i + 1]
                    # Valid JSON escape sequences: " \ / b f n r t u
                    if next_char in ['"', '\\', '/', 'b', 'f', 'n', 'r', 't', 'u']:
                        result.append(s[i:i+2])
                        i += 2
                    else:
                        # Invalid escape sequence, escape the backslash itself
                        result.append('\\\\')
                        result.append(next_char)
                        i += 2
                else:
                    result.append(s[i])
                    i += 1
            return ''.join(result)
        
        json_str = fix_invalid_escapes(json_str)
        
        try:
            data = json.loads(json_str)
            items = data.get("slides") or data.get("sections") or []
            
            sections = []
            total = len(items)
            for idx, item in enumerate(items):
                # Parse tables
                tables = []
                for t in item.get("tables", []):
                    tables.append(TableRef(
                        table_id=t.get("table_id", ""),
                        extract=t.get("extract", ""),
                        focus=t.get("focus", ""),
                    ))
                
                # Parse figures
                figures = []
                for f in item.get("figures", []):
                    figures.append(FigureRef(
                        figure_id=f.get("figure_id", ""),
                        focus=f.get("focus", ""),
                    ))
                
                # Auto-determine section_type based on position (slides only)
                if is_slides:
                    if idx == 0:
                        section_type = "opening"
                    elif idx == total - 1:
                        section_type = "ending"
                    else:
                        section_type = "content"
                else:
                    section_type = "content"
                
                sections.append(Section(
                    id=item.get("id", f"section_{idx+1}"),
                    title=item.get("title", ""),
                    section_type=section_type,
                    content=item.get("content", ""),
                    tables=tables,
                    figures=figures,
                ))
            return sections
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.error(f"Failed to parse JSON string (first 500 chars): {json_str[:500]}")
            logger.warning("Using fallback sections due to JSON parse error")
            return self._fallback_sections()
        except Exception as e:
            logger.error(f"Unexpected error in _parse_sections: {e}")
            logger.warning("Using fallback sections due to unexpected error")
            return self._fallback_sections()
    
    def _fallback_sections(self) -> List[Section]:
        """Return minimal fallback sections if parsing fails."""
        return [
            Section(id="section_01", title="Title", section_type="opening", content=""),
            Section(id="section_02", title="Content", section_type="content", content=""),
        ]
    
    def _load_figure_images(self, origin) -> List[Dict]:
        """Load figure images as base64 with caption."""
        images = []
        for fig in origin.figures:
            # Build full path
            if origin.base_path:
                img_path = Path(origin.base_path) / fig.image_path
            else:
                img_path = Path(fig.image_path)
            
            if not img_path.exists():
                continue
            
            # Determine mime type
            suffix = img_path.suffix.lower()
            mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", 
                       ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}
            mime_type = mime_map.get(suffix, "image/jpeg")
            
            # Read and encode
            try:
                with open(img_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode("utf-8")
                images.append({
                    "figure_id": fig.figure_id,
                    "caption": fig.caption,
                    "base64": img_data,
                    "mime_type": mime_type,
                })
            except Exception:
                continue
        
        return images
    
    def _truncate(self, text: str, max_len: int) -> str:
        """Truncate text to max length."""
        if len(text) <= max_len:
            return text
        return text[:max_len] + "\n\n[Content truncated...]"
