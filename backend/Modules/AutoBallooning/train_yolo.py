"""
Fine-tune the Auto Ballooning YOLO model on your own annotated drawings.

Improving detection accuracy (which callouts get found) requires training on
labelled drawings — there is no language/framework shortcut for this. This script
fine-tunes the existing model on a YOLO-format dataset you provide.

────────────────────────────────────────────────────────────────────────────
1) Prepare a dataset in Ultralytics YOLO format
────────────────────────────────────────────────────────────────────────────
   datasets/drawings/
     images/train/*.png|jpg      labels/train/*.txt
     images/val/*.png|jpg        labels/val/*.txt

   Each label .txt line:  <class_id> <x_center> <y_center> <width> <height>
   (all normalised 0..1). Use a tool like Roboflow, LabelImg, or CVAT to annotate.

2) Create the dataset config (or let this script scaffold one):
       python train_yolo.py --make-data-yaml ../../datasets/drawings/data.yaml

3) Train (fine-tunes from the current AutoBallooningModel.pt by default):
       python train_yolo.py --data ../../datasets/drawings/data.yaml --epochs 120 --imgsz 1280

4) Use the new weights:
       Copy runs/.../weights/best.pt to Resources/models/AutoBallooningModel.pt
       (or set AUTOBALLOON_YOLO_WEIGHTS=/full/path/to/best.pt)

Run with no GPU and it trains on CPU (slower). With an NVIDIA GPU it uses CUDA
automatically.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Same 10 classes as AutoBallooningModel.pt (order = class id 0..9).
CLASS_NAMES = [
    "Dimensions",
    "GDnT",
    "Notes",
    "Title_Block",
    "Special_Characteristics",
    "Datums",
    "Welding_Symbols",
    "Surface_Finish_Symbols",
    "Revision_Table",
    "Miscellaneous",
]


def _base_weights() -> str:
    """Resolve the current Auto Ballooning weights to fine-tune from."""
    try:
        from tasks import resolve_autoballoon_weights_path  # type: ignore

        return resolve_autoballoon_weights_path()
    except Exception:
        here = Path(__file__).resolve().parent
        cand = here / "Resources" / "models" / "AutoBallooningModel.pt"
        return str(cand)


def make_data_yaml(path: str) -> None:
    """Scaffold a YOLO data.yaml with the correct class names."""
    out = Path(path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    names_block = "\n".join(f"  {i}: {n}" for i, n in enumerate(CLASS_NAMES))
    content = (
        f"# Auto Ballooning dataset config\n"
        f"path: {out.parent.as_posix()}\n"
        f"train: images/train\n"
        f"val: images/val\n"
        f"names:\n{names_block}\n"
    )
    out.write_text(content, encoding="utf-8")
    print(f"Wrote dataset config -> {out}")
    print("Now place images/labels under that folder and run training with --data", str(out))


def train(args: argparse.Namespace) -> int:
    try:
        from ultralytics import YOLO  # type: ignore
    except Exception as exc:
        print(f"ERROR: ultralytics not installed ({exc}). pip install ultralytics")
        return 2

    data = Path(args.data).expanduser().resolve()
    if not data.is_file():
        print(f"ERROR: data config not found: {data}")
        print("Create one with:  python train_yolo.py --make-data-yaml path/to/data.yaml")
        return 2

    weights = args.weights or _base_weights()
    if not Path(weights).is_file():
        print(f"WARNING: base weights '{weights}' not found — falling back to yolov8m.pt")
        weights = "yolov8m.pt"

    print(f"Fine-tuning from: {weights}")
    print(f"Dataset:          {data}")
    print(f"epochs={args.epochs} imgsz={args.imgsz} batch={args.batch} device={args.device or 'auto'}")

    model = YOLO(weights)
    model.train(
        data=str(data),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device if args.device else None,
        project=args.project,
        name=args.name,
        patience=args.patience,
        exist_ok=True,
    )
    print("\nTraining complete.")
    print(f"Best weights: {args.project}/{args.name}/weights/best.pt")
    print(
        "To use them: copy best.pt to Resources/models/AutoBallooningModel.pt "
        "or set AUTOBALLOON_YOLO_WEIGHTS to its path."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fine-tune Auto Ballooning YOLO model.")
    p.add_argument("--data", help="Path to YOLO data.yaml")
    p.add_argument("--weights", help="Base weights to fine-tune from (default: current model)")
    p.add_argument("--epochs", type=int, default=120)
    p.add_argument("--imgsz", type=int, default=1280)
    p.add_argument("--batch", type=int, default=8)
    p.add_argument("--device", default="", help="cuda device e.g. 0, or cpu (default: auto)")
    p.add_argument("--project", default="runs/autoballoon")
    p.add_argument("--name", default="finetune")
    p.add_argument("--patience", type=int, default=30)
    p.add_argument("--make-data-yaml", metavar="PATH", help="Scaffold a data.yaml then exit")
    args = p.parse_args(argv)

    # Make local imports (tasks.py) resolvable.
    sys.path.insert(0, str(Path(__file__).resolve().parent))

    if args.make_data_yaml:
        make_data_yaml(args.make_data_yaml)
        return 0
    if not args.data:
        p.error("--data is required (or use --make-data-yaml to scaffold one)")
    return train(args)


if __name__ == "__main__":
    raise SystemExit(main())
