"""Export frontend + backend copies for GitHub split repos (run from repo: python backend/tools/export_split_repos.py)."""
from __future__ import annotations

import json
import os
import shutil
import stat
from pathlib import Path


def _rmtree_robust(path: Path) -> None:
    def _onexc(_func, p: str, exc: BaseException) -> None:
        try:
            os.chmod(p, stat.S_IWRITE)
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p, onexc=_onexc)
            else:
                os.unlink(p)
        except OSError:
            pass

    if path.exists():
        shutil.rmtree(path, onexc=_onexc)


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
OUT = ROOT.parent / "split_repos"
OUT_FE = OUT / "Autoballon_FrontEnd"
OUT_BE = OUT / "Auto_ballon_backend"


def scrub_key(k: str) -> bool:
    kl = k.lower().replace("-", "_")
    if any(
        x in kl
        for x in (
            "_key",
            "secret",
            "token",
            "private_key",
            "password",
            "api_keys",
        )
    ):
        return True
    if kl in (
        "access_key_id",
        "secret_access_key",
        "openai_api_key",
        "from_emails",
        "project_id",
        "client_email",
        "client_id",
        "client_x509_cert_url",
    ):
        return True
    return False


def scrub(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "GCP_SERVICE_ACCOUNT" and isinstance(v, dict):
                out[k] = {
                    ik: (
                        ""
                        if scrub_key(ik) or ik in ("project_id", "client_email", "client_id")
                        else (scrub(iv) if isinstance(iv, (dict, list)) else iv)
                    )
                    for ik, iv in v.items()
                }
                continue
            if k == "GCP" and isinstance(v, dict):
                inner = {}
                for ik, iv in v.items():
                    if ik == "PROJECT_ID":
                        inner[ik] = ""
                    elif isinstance(iv, dict):
                        inner[ik] = scrub(iv)
                    elif isinstance(iv, list):
                        inner[ik] = scrub(iv)
                    else:
                        inner[ik] = iv
                out[k] = inner
                continue
            if scrub_key(k):
                out[k] = "" if isinstance(v, str) else ([] if isinstance(v, list) else v)
            elif isinstance(v, (dict, list)):
                out[k] = scrub(v)
            else:
                out[k] = v
        return out
    if isinstance(obj, list):
        return [scrub(x) for x in obj]
    return obj


def copy_balloon_ui(src_dir: Path, dest_dir: Path) -> None:
    for p in src_dir.rglob("*"):
        if not p.is_file():
            continue
        if ".git" in p.parts:
            continue
        rel = p.relative_to(src_dir)
        dest = dest_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)


_SKIP_TOP = {".Temp", "__pycache__", "Logs", "tools"}


def copy_backend_for_github(dest_be: Path, *, embed_ui_from: Path) -> None:
    _rmtree_robust(dest_be)
    dest_be.mkdir(parents=True, exist_ok=True)
    for item in BACKEND.iterdir():
        if item.name in _SKIP_TOP:
            continue
        target = dest_be / item.name
        if item.is_dir():
            shutil.copytree(
                item,
                target,
                ignore=lambda _d, names: [n for n in names if n == "__pycache__"],
                dirs_exist_ok=False,
            )
        else:
            shutil.copy2(item, target)
    with (BACKEND / "default_config.json").open(encoding="utf-8") as f:
        clean = scrub(json.load(f))
    (dest_be / "default_config.json").write_text(json.dumps(clean, indent=4), encoding="utf-8")
    ui_dest = dest_be / "Resources" / "balloon_ui"
    _rmtree_robust(ui_dest)
    ui_dest.mkdir(parents=True, exist_ok=True)
    copy_balloon_ui(embed_ui_from, ui_dest)


def export_split_repos() -> None:
    OUT_FE.mkdir(parents=True, exist_ok=True)
    OUT_BE.mkdir(parents=True, exist_ok=True)
    copy_balloon_ui(FRONTEND, OUT_FE)
    copy_backend_for_github(OUT_BE, embed_ui_from=FRONTEND)
    print("Wrote:", OUT_FE)
    print("Wrote:", OUT_BE)


def main() -> None:
    export_split_repos()


if __name__ == "__main__":
    main()
