"""
State management for pipeline execution
"""
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

from ..utils import load_json, save_json
from .paths import (
    get_rag_checkpoint,
    get_summary_checkpoint,
    get_plan_checkpoint,
)

STAGES = ["rag", "summary", "plan", "generate"]


def get_state_path(config_dir: Path) -> Path:
    """Get path to state file."""
    return config_dir / "state.json"


def load_state(config_dir: Path) -> Optional[Dict]:
    """Load pipeline state from file."""
    return load_json(get_state_path(config_dir))


def save_state(config_dir: Path, state: Dict):
    """Save pipeline state to file."""
    state["updated_at"] = datetime.now().isoformat()
    save_json(get_state_path(config_dir), state)


def create_state(config: Dict) -> Dict:
    """Create initial pipeline state."""
    return {
        "config": config,
        "created_at": datetime.now().isoformat(),
        "stages": {s: "pending" for s in STAGES},
    }


def detect_start_stage(base_dir: Path, config_dir: Path, config: Dict) -> str:
    """Detect which stage to start from based on existing checkpoints."""
    # Check mode-specific checkpoints
    rag_checkpoint_path = get_rag_checkpoint(base_dir, config)
    if not rag_checkpoint_path.exists():
        return "rag"

    rag_checkpoint = load_json(rag_checkpoint_path)
    checkpoint_input = rag_checkpoint["input_path"]
    current_input = config["input_path"]
    if Path(checkpoint_input).resolve() != Path(current_input).resolve():
        return "rag"
    
    if not get_summary_checkpoint(base_dir, config).exists():
        return "summary"
    
    # Check config-specific checkpoint
    if not get_plan_checkpoint(config_dir).exists():
        return "plan"
    
    # All checkpoints exist, only need to regenerate images
    return "generate"
