"""Markdown output discovery for MinerU layouts that fast mode used to miss."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

_PARSER_PATH = (
    Path(__file__).resolve().parents[1] / "paper2slides" / "raganything" / "parser.py"
)
_SPEC = importlib.util.spec_from_file_location("mineru_parser_under_test", _PARSER_PATH)
_PARSER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_PARSER)
MineruParser = _PARSER.MineruParser


class MineruMarkdownTests(unittest.TestCase):
    def test_hybrid_auto_markdown_and_content_list(self):
        # MinerU 2.7+ hybrid-* writes hybrid_auto/, not auto/.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "paper" / "hybrid_auto"
            (bundle / "images").mkdir(parents=True)
            (bundle / "images" / "fig.png").write_bytes(b"png")
            (bundle / "paper.md").write_text("# Title\n\nbody\n", encoding="utf-8")
            content_list = [
                {"type": "text", "text": "body"},
                {"type": "image", "img_path": "images/fig.png"},
            ]
            (bundle / "paper_content_list.json").write_text(
                json.dumps(content_list), encoding="utf-8"
            )

            blocks, markdown = MineruParser._read_output_files(root, "paper", method="auto")

            self.assertIn("# Title", markdown)
            self.assertEqual(blocks[1]["img_path"], str((bundle / "images" / "fig.png").resolve()))

    def test_empty_auto_dir_does_not_hide_hybrid_auto(self):
        # The stem directory existing used to force a lookup in auto/ only.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "paper" / "auto").mkdir(parents=True)
            bundle = root / "paper" / "hybrid_auto"
            bundle.mkdir()
            (bundle / "full.md").write_text("hybrid body\n", encoding="utf-8")

            _blocks, markdown = MineruParser._read_output_files(root, "paper", method="auto")

            self.assertEqual(markdown, "hybrid body\n")

    def test_mineru4_markdown_md(self):
        # MinerU 4.0 save() writes markdown.md under the tier directory.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "paper" / "standard"
            bundle.mkdir(parents=True)
            (bundle / "markdown.md").write_text("tier markdown\n", encoding="utf-8")

            _blocks, markdown = MineruParser._read_output_files(root, "paper", method="auto")

            self.assertEqual(markdown, "tier markdown\n")

    def test_content_blocks_generate_markdown_file(self):
        # Content list without a markdown file used to surface as
        # "No markdown files generated" in fast mode.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "paper" / "hybrid_auto"
            bundle.mkdir(parents=True)
            content_list = [
                {"type": "text", "text": "Abstract"},
                {
                    "type": "table",
                    "table_caption": ["Table 1: Results"],
                    "table_body": "<table><tr><td>1</td></tr></table>",
                },
                {
                    "type": "image",
                    "img_path": "images/plot.png",
                    "image_caption": ["Figure 1: Plot"],
                },
            ]
            (bundle / "paper_content_list.json").write_text(
                json.dumps(content_list), encoding="utf-8"
            )

            blocks, markdown = MineruParser._read_output_files(root, "paper", method="auto")

            md_file = bundle / "paper.md"
            self.assertTrue(md_file.is_file())
            self.assertIn("Abstract", markdown)
            self.assertIn("<table>", markdown)
            self.assertIn("![Figure 1: Plot](images/plot.png)", markdown)
            self.assertEqual(len(blocks), 3)
            self.assertTrue(md_file.read_text(encoding="utf-8").startswith("Abstract"))

    def test_legacy_command_uses_pipeline_backend(self):
        MineruParser._mineru_cli_style = "legacy"
        try:
            cmd = MineruParser._build_legacy_cmd(
                input_path="paper.pdf",
                output_dir="out",
                method="auto",
                lang=None,
                backend="pipeline",
                start_page=None,
                end_page=None,
                formula=True,
                table=True,
                device=None,
                source=None,
                vlm_url=None,
            )
        finally:
            MineruParser._mineru_cli_style = None

        self.assertEqual(
            cmd[:7],
            ["mineru", "-p", "paper.pdf", "-o", "out", "-m", "auto"],
        )
        self.assertEqual(cmd[7:9], ["-b", "pipeline"])

    def test_parse_command_writes_markdown_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            cmd = MineruParser._build_parse_cmd("paper.pdf", tmp, tier="flash")

        # mineru-kit when installed, otherwise `mineru parse`.
        self.assertIn("parse", cmd)
        self.assertTrue(any(part.endswith("paper.md") for part in cmd))
        self.assertIn("--pages", cmd)
        self.assertIn("all", cmd)
        self.assertIn("--tier", cmd)
        self.assertIn("flash", cmd)


if __name__ == "__main__":
    unittest.main()
