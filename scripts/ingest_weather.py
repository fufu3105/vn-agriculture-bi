"""Run the BP4 NASA POWER ingestion and Spark processing pipeline."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.bp4.pipeline import run

if __name__ == "__main__":
    sys.exit(run())
