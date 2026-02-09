import subprocess
import sys
import os
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# Import settings to get configuration
try:
    from config.settings import LOG_LEVEL
    from src.utils.timezone_utils import format_kst_datetime
except ImportError:
    LOG_LEVEL = "INFO"
    # Fallback if timezone_utils not available
    from datetime import datetime
    def format_kst_datetime(fmt="%Y-%m-%d %H:%M:%S"):
        return datetime.now().strftime(fmt)

def run_script(script_name):
    """Run a python script and check for errors"""
    script_path = BASE_DIR / script_name
    print(f"[{format_kst_datetime('%H:%M:%S')}] Starting {script_name}...")
    
    try:
        # Run the script using the same python interpreter
        result = subprocess.run(
            [sys.executable, str(script_path)],
            check=True,
            capture_output=False  # Let output flow to console
        )
        print(f"[{format_kst_datetime('%H:%M:%S')}] {script_name} completed successfully.\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] {script_name} failed with exit code {e.returncode}")
        return False
    except Exception as e:
        print(f"\n[ERROR] Failed to execute {script_name}: {e}")
        return False

def main():
    start_time = time.time()
    print("="*60)
    print(f" Daily News Agent Automation - {format_kst_datetime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # List of scripts to run in order
    scripts = [
        "run_p1.py",  # Collect News
        "run_p2.py",  # Deduplicate & Filter
        "run_p3.py",  # Pre-processing (deprecated? check logic) - Wait, run_p3 is usually keyword filtering
        "run_p4.py",  # LLM Classification
        "run_p5.py",  # Clustering/Topic Generation
        "run_p6.py",   # Report Generation
        "run_p6_1.py", # Telegram Reporting
        "run_p6_2.py", # WordPress Auto-Posting (KR)
        "run_p6_3.py", # WordPress Auto-Posting (EN)
        # "run_p7.py",   # Evergreen Content Generation (Blog/YouTube) - DISABLED: Logic improvement needed
        "run_summary.py" # Final Summary Export
    ]
    
    for script in scripts:
        if not (BASE_DIR / script).exists():
            print(f"[WARNING] Script not found: {script}. Skipping...")
            continue
            
        success = run_script(script)
        if not success:
            print("[CRITICAL] Pipeline stopped due to error.")
            sys.exit(1)
            
        # Optional: Add delay between phases if needed
        time.sleep(2)
    
    elapsed = time.time() - start_time
    print("="*60)
    print(f" Pipeline Completed Successfully in {elapsed:.2f} seconds")
    print("="*60)

if __name__ == "__main__":
    main()
