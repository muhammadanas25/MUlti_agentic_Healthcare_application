#!/usr/bin/env python3
"""
Quick launcher for CLI testing interface.

Usage:
    python test_cli.py

    OR

    ./test_cli.py  (if made executable)
"""
import sys
import os

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.interfaces.cli_tester import main

if __name__ == "__main__":
    main()
