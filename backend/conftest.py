"""Ensure the backend directory is importable as the `app` package root."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
