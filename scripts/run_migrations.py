#!/usr/bin/env python3
"""
Script to run database migrations
Usage: python scripts/run_migrations.py
"""

import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migrations import run_migrations

if __name__ == "__main__":
    print("🚀 Running InkDrive database migrations...")
    success = run_migrations()
    
    if success:
        print("🎉 Migrations completed successfully!")
        sys.exit(0)
    else:
        print("💥 Migrations failed!")
        sys.exit(1)
