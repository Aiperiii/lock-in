from pathlib import Path

# backend/app/paths.py -> app -> backend -> backend/uploads
UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
