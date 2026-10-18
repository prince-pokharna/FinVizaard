import sys
import os
from pathlib import Path

sub = Path(__file__).resolve().parent / "FinVizaard-Prince"
if str(sub) not in sys.path:
    sys.path.insert(0, str(sub))
os.chdir(sub)

import uvicorn

if __name__ == "__main__":
    uvicorn.run("Backend.src.main:app", host="0.0.0.0", port=8000, reload=True)
