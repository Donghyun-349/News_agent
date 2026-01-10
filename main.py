#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Main Execution Script for News Agent
Sequential Execution: Phase 1 -> Phase 6
"""

import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

# Setup Logger (Simple print for master script)
def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [MAIN] {msg}")

def run_phase(script_name: str):
    """Run a specific phase script using subprocess"""
    script_path = Path(script_name)
    
    if not script_path.exists():
        log(f"❌ Script not found: {script_name}")
        sys.exit(1)

    log(f"🚀 Starting {script_name}...")
    start_time = time.time()
    
    try:
        # Check python executable
        python_exe = sys.executable
        
        # Run script
        result = subprocess.run(
            [python_exe, script_name], 
            check=True,  # Raise CalledProcessError on non-zero exit code
            text=True
        )
        
        duration = time.time() - start_time
        log(f"✅ Finished {script_name} (Duration: {duration:.2f}s)")
        
    except subprocess.CalledProcessError as e:
        log(f"❌ Error occurred while running {script_name}")
        log(f"Exit Code: {e.returncode}")
        sys.exit(1)
    except Exception as e:
        log(f"❌ Unexpected error in {script_name}: {e}")
        sys.exit(1)

def main():
    log("="*60)
    log("News Agent Pipeline Started")
    log("="*60)

    # List of phases to run in order
    phases = [
        "run_p1.py", # Phase 1: Collection
        # Phase 2 & 3 are now typically integrated or run separately? 
        # Based on file list, existing pipeline seems to be p1 -> p2 -> p3 -> p4 -> p5 -> p6
        # Let's check if run_p2.py exists and what it does.
        # Assuming standard flow based on previous conversation history.
        "run_p2.py", # Phase 2: Deduplication
        "run_p3.py", # Phase 3: Keyword Filtering
        "run_p4.py", # Phase 4: LLM Classification
        "run_p5.py", # Phase 5: Event Clustering
        "run_p6.py", # Phase 6: Report Generation
    ]
    
    total_start = time.time()

    for script in phases:
        run_phase(script)
        # Small delay between phases for safety
        time.sleep(1)

    total_duration = time.time() - total_start
    log("="*60)
    log(f"🎉 All Phases Completed Successfully! (Total Duration: {total_duration/60:.2f} min)")
    log("="*60)

if __name__ == "__main__":
    main()
