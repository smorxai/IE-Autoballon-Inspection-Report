

import json
import os
from pathlib import Path


ConfigDict = {}


def _apply_env_overrides():
    """Optional env overrides so Docker/CI can point at redis/mongo without editing JSON."""
    global ConfigDict
    if not ConfigDict:
        return
    rh = os.environ.get("REDIS_HOST")
    if rh and isinstance(ConfigDict.get("BROKER"), dict):
        ConfigDict["BROKER"]["ADDRESS"] = rh
    rp = os.environ.get("REDIS_PORT")
    if rp and isinstance(ConfigDict.get("BROKER"), dict):
        try:
            ConfigDict["BROKER"]["PORT"] = int(rp)
        except ValueError:
            pass
    mu = os.environ.get("MONGODB_URI")
    if mu and isinstance(ConfigDict.get("DATABASE"), dict):
        ConfigDict["DATABASE"]["URI"] = mu
    gk = os.environ.get("GEMINI_API_KEY")
    if gk and isinstance(ConfigDict.get("GEMINI"), dict):
        ConfigDict["GEMINI"]["GEMINI_25_PRO_API_KEY"] = gk
    gq = os.environ.get("GROQ_API_KEY")
    if gq and isinstance(ConfigDict.get("GROQ"), dict):
        ConfigDict["GROQ"]["API_KEY"] = gq
    oa = os.environ.get("OPENAI_API_KEY")
    if oa and isinstance(ConfigDict.get("OPENAI"), dict):
        ConfigDict["OPENAI"]["openai_api_key"] = oa
        ConfigDict["OPENAI"]["USE_FOR_VISION"] = True
        ConfigDict["OPENAI"]["USE_FOR_CHAT"] = True
    ant = os.environ.get("ANTHROPIC_API_KEY")
    if ant:
        if not isinstance(ConfigDict.get("ANTHROPIC"), dict):
            ConfigDict["ANTHROPIC"] = {}
        ConfigDict["ANTHROPIC"]["API_KEY"] = ant


def InitConfiguration(configFile: str | None = None):
    """Load JSON from this directory (backend/) by default."""
    global ConfigDict
    _dir = Path(__file__).resolve().parent
    if not configFile or configFile in ("./config.json", "config.json"):
        primary = _dir / "config.json"
        fallback = _dir / "default_config.json"
        path = primary if primary.is_file() else fallback
    else:
        p = Path(configFile)
        if p.is_absolute() and p.is_file():
            path = p
        elif (_dir / p.name).is_file():
            path = _dir / p.name
        elif p.is_file():
            path = p.resolve()
        else:
            path = _dir / "default_config.json"
    with open(path, "r", encoding="utf-8") as file:
        ConfigDict = json.load(file)
    _apply_env_overrides()


def GetConfiguration(nodeName: str | None = None):
    if nodeName:
        if nodeName in ConfigDict:
            return ConfigDict[nodeName]
    return None
