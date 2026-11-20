import sys
from pathlib import Path

# Add core subdirectory to path so tests can find nlp, commands, etc.
sys.path.insert(0, str(Path(__file__).parent / "core"))
