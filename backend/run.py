from pathlib import Path
import uvicorn
from app.settings import load_settings

if __name__ == "__main__":
    server, _, env = load_settings()
    uvicorn.run(
        "app.main:app",
        host=env["listen-host"], port=env["port"], reload=env["reload"],
        app_dir=str(Path(__file__).parent),
    )
