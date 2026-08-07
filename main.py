#!/usr/bin/env python3
"""FingerGuard Browser — entry point.

Uses pywebview (lightweight ~5MB system WebView) instead of PyQt5 (~100MB).
The web UI is served by the built-in API server on 127.0.0.1.
"""
import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.web.launcher import launch

if __name__ == "__main__":
    launch()
