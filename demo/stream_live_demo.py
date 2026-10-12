#!/usr/bin/env python
"""Wrapper to run real-time live streamer from demo directory."""

import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from stream_live_demo import main

if __name__ == "__main__":
    main()
