import os
import sys
from pathlib import Path

# Explicitly load .env
try:
    from dotenv import load_dotenv, find_dotenv
    print(f"python-dotenv is installed.")
    
    env_path = find_dotenv()
    print(f"Found .env at: {env_path}")
    
    loaded = load_dotenv(verbose=True)
    print(f"load_dotenv result: {loaded}")
    
except ImportError:
    print("python-dotenv is NOT installed.")

# Check key
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    print(f"OPENAI_API_KEY is SET (length: {len(api_key)})")
else:
    print("OPENAI_API_KEY is NOT SET")

# Check via settings
try:
    sys.path.insert(0, os.getcwd())
    from config.settings import OPENAI_API_KEY as SETTINGS_KEY
    if SETTINGS_KEY:
        print(f"Settings.py has key: YES (length: {len(SETTINGS_KEY)})")
    else:
        print("Settings.py has key: NO")
except Exception as e:
    print(f"Error importing settings: {e}")
