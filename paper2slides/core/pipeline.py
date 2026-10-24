"""
Pipeline execution and output listing
"""
import logging
from pathlib import Path
from typing import Dict

from ..utils import log_section
from .state import STAGES, load_state, save_state, create_state
from .paths import get_rag_checkpoint, get_summary_checkpoint, get_plan_checkpoint
from .stages import run_rag_stage, run_summary_stage, run_plan_stage, run_generate_stage

logger = logging.getLogger(__name__)


async def run_pipeline(base_dir: Path, config_dir: Path, config: Dict, from_stage: str, session_id: str = None, session_manager = None):
    """Run pipeline from specified stage.
    
    Args:
        base_dir: Base directory for this document/project
        config_dir: Config-specific directory
        config: Pipeline configuration
        from_stage: Stage to start from
        session_id: Session ID for cancellation tracking
        session_manager: Session manager to check cancellation status

    Returns:
        True if every requested stage completed; False if a stage failed.
    """
    
    # Initialize or load state
    state = load_state(config_dir)
    if not state:
        state = create_state(config)
        save_state(config_dir, state)
    else:
        # When regenerating, reset the status of stages that will be executed
        # This ensures the frontend progress bar shows correct progress
        start_idx = STAGES.index(from_stage)
        for i in range(start_idx, len(STAGES)):
            state["stages"][STAGES[i]] = "pending"
        # Update session_id if provided
        if session_id:
            state["session_id"] = session_id
        save_state(config_dir, state)
    
    start_idx = STAGES.index(from_stage)
    logger.info("")
    logger.info(f"Starting from stage: {from_stage}")
    success = True
    
    for i in range(start_idx, len(STAGES)):
        # Check if cancelled before starting each stage
        if session_manager and session_id and session_manager.is_cancelled(session_id):
            logger.info(f"Pipeline cancelled at stage: {STAGES[i]}")
            state["stages"][STAGES[i]] = "cancelled"
            state["error"] = "Cancelled by user"
            save_state(config_dir, state)
            raise Exception("Pipeline cancelled by user")
        
        stage = STAGES[i]
        log_section(f"STAGE: {stage.upper()}")
        
        state["stages"][stage] = "running"
        save_state(config_dir, state)
        
        try:
            if stage == "rag":
                await run_rag_stage(base_dir, config)
            elif stage == "summary":
                await run_summary_stage(base_dir, config)
            elif stage == "plan":
                await run_plan_stage(base_dir, config_dir, config)
            elif stage == "generate":
                await run_generate_stage(base_dir, config_dir, config)
            
            state["stages"][stage] = "completed"
            save_state(config_dir, state)
            
        except Exception as e:
            state["stages"][stage] = "failed"
            state["error"] = str(e)
            save_state(config_dir, state)
            logger.error(f"Stage failed: {e}", exc_info=True)
            success = False
            break
    
    # Print summary
    log_section("SUMMARY")
    for stage in STAGES:
        status = state["stages"].get(stage, "pending")
        icon = "✓" if status == "completed" else "✗" if status == "failed" else "○"
        logger.info(f"  [{icon}] {stage}: {status}")

    return success


def list_outputs(output_dir: str):
    """List all projects and their output configurations."""
    output_path = Path(output_dir)
    if not output_path.exists():
        logger.info("No outputs found.")
        return
    
    found = False
    for project_dir in sorted(output_path.iterdir()):
        if not project_dir.is_dir():
            continue
        
        for content_dir in sorted(project_dir.iterdir()):
            if not content_dir.is_dir():
                continue
            
            # Check for mode directories (fast/normal)
            mode_dirs = []
            for mode_name in ["fast", "normal"]:
                mode_dir = content_dir / mode_name
                if mode_dir.exists() and mode_dir.is_dir():
                    # Check mode-specific checkpoints (need to create dummy config for path functions)
                    dummy_config = {"fast_mode": (mode_name == "fast")}
                    has_rag = get_rag_checkpoint(content_dir, dummy_config).exists()
                    has_summary = get_summary_checkpoint(content_dir, dummy_config).exists()
                    
                    # Find config directories under mode
                    configs = []
                    for config_dir in sorted(mode_dir.iterdir()):
                        if config_dir.is_dir() and not config_dir.name.startswith(".") and config_dir.name not in ["checkpoint_rag.json", "checkpoint_summary.json", "summary.md"]:
                            state = load_state(config_dir)
                            if state:
                                configs.append((config_dir.name, state))
                    
                    if has_rag or has_summary or configs:
                        mode_dirs.append((mode_name, has_rag, has_summary, configs))
            
            if mode_dirs:
                found = True
                logger.info("")
                logger.info(f"{project_dir.name}/{content_dir.name}/")
                
                for mode_name, has_rag, has_summary, configs in mode_dirs:
                    rag_icon = "✓" if has_rag else "○"
                    sum_icon = "✓" if has_summary else "○"
                    logger.info(f"  [{mode_name}] rag[{rag_icon}] summary[{sum_icon}]")
                    
                    if configs:
                        for name, state in configs:
                            stages = state.get("stages", {})
                            plan_ok = stages.get("plan") == "completed"
                            gen_ok = stages.get("generate") == "completed"
                            plan_icon = "✓" if plan_ok else "○"
                            gen_icon = "✓" if gen_ok else "○"
                            logger.info(f"    {name}/ plan[{plan_icon}] generate[{gen_icon}]")
    
    if not found:
        logger.info("No outputs found.")
