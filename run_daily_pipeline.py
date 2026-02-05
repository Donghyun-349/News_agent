#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Daily Market Intelligence - Automated Pipeline Orchestrator

Execution Order:
1. Phase 6:   Generate Korean Daily Brief
2. Phase 6-1: Send to Telegram
3. Phase 7:   Generate English Global Brief
4. Phase 7-1: Post to WordPress (English)

Note: Phase 6-2 is SKIPPED (not executed)
"""

import sys
import subprocess
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent

PHASES = [
    {
        "name": "Phase 6 - Korean Daily Brief",
        "script": "run_p6.py",
        "description": "Generate Korean market intelligence report"
    },
    {
        "name": "Phase 6-1 - Telegram Delivery",
        "script": "run_p6_1.py",
        "description": "Send report to Telegram channel"
    },
    {
        "name": "Phase 7 - English Global Brief",
        "script": "run_p7.py",
        "description": "Generate English global market intelligence report"
    },
    {
        "name": "Phase 7-1 - WordPress Posting",
        "script": "run_p7_1.py",
        "description": "Post English report to WordPress"
    }
]

def run_phase(phase_info: dict) -> bool:
    """
    Execute a single phase script.
    Returns True if successful, False otherwise.
    """
    script_path = PROJECT_ROOT / phase_info["script"]
    
    if not script_path.exists():
        logger.error(f"❌ Script not found: {script_path}")
        return False
    
    logger.info("="*80)
    logger.info(f"🚀 {phase_info['name']}")
    logger.info(f"📝 {phase_info['description']}")
    logger.info("="*80)
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        # Print output
        if result.stdout:
            print(result.stdout)
        
        if result.returncode == 0:
            logger.info(f"✅ {phase_info['name']} completed successfully")
            return True
        else:
            logger.error(f"❌ {phase_info['name']} failed with exit code {result.returncode}")
            if result.stderr:
                logger.error(f"Error output:\n{result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Exception running {phase_info['name']}: {e}")
        return False

def main():
    """
    Run all phases in sequence.
    Stop on first failure.
    """
    start_time = datetime.now()
    
    logger.info("="*80)
    logger.info("🌐 Daily Market Intelligence - Automated Pipeline")
    logger.info(f"📅 Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*80)
    logger.info("")
    
    for i, phase in enumerate(PHASES, start=1):
        logger.info(f"[{i}/{len(PHASES)}] Starting {phase['name']}...")
        
        success = run_phase(phase)
        
        if not success:
            logger.error("="*80)
            logger.error(f"❌ Pipeline FAILED at {phase['name']}")
            logger.error("="*80)
            sys.exit(1)
        
        logger.info("")
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    logger.info("="*80)
    logger.info("✅ All phases completed successfully!")
    logger.info(f"⏱️  Total duration: {duration:.1f} seconds")
    logger.info("="*80)

if __name__ == "__main__":
    main()
