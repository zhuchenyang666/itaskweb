import os
import sys
from pathlib import Path
import yaml

ROOT = Path(sys.executable).resolve().parent / "backend" if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]

def load_settings():
    config_path = ROOT / "resources/config.yaml"
    if not config_path.is_file():
        config_path = config_path.with_name("config.example.yaml")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    server = config["server"]
    active = os.environ.get("ITIME_ENV", server["active"])
    if active not in ("local", "production"):
        raise ValueError("ITIME_ENV必须是local或production")
    environment = server["environments"][active]
    return server, active, environment

def data_root():
    _, active, environment = load_settings()
    return ROOT / environment.get("data-dir", "data/mock" if active == "local" else "data")
