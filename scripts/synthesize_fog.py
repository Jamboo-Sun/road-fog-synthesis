"""Render synthetic fog without moving the input image pixels."""

import argparse
import json
import shutil
import uuid
from pathlib import Path

import numpy as np
from PIL import Image


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
LEVEL_NAMES = ("light", "medium", "heavy")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", type=Path, required=True, help="Image or image directory")
    depth = parser.add_mutually_exclusive_group(required=True)
    depth.add_argument("--depth-dir", type=Path, help="Depth .npy files matching image paths")
    depth.add_argument("--row-proxy", action="store_true", help="Use a row-based depth proxy for previews")
    parser.add_argument("--depth-unit", choices=("meters", "relative"), help="Required with --depth-dir")
    parser.add_argument("--labels", type=Path, help="Directory of matching YOLO .txt files")
    parser.add_argument("--output", type=Path, required=True, help="New directory for generated files")
    parser.add_argument("--levels", type=float, nargs=3, metavar=("LIGHT", "MEDIUM", "HEAVY"))
    parser.add_argument("--airlight", type=float, nargs=3, default=(0.8, 0.8, 0.8),
                        metavar=("R", "G", "B"), help="sRGB airlight on [0, 1], default: 0.8 0.8 0.8")
    args = parser.parse_args()
    if bool(args.depth_dir) != bool(args.depth_unit):
        parser.error("--depth-dir and --depth-unit must be used together")
    if args.levels is None:
        args.levels = (0.005, 0.01, 0.02) if args.depth_unit == "meters" else (0.25, 0.5, 1.0)
    light, medium, heavy = args.levels
    if not np.isfinite(args.levels).all() or not 0 <= light < medium < heavy:
        parser.error("--levels must contain three increasing finite, nonnegative values")
    if not all(0 <= value <= 1 for value in args.airlight):
        parser.error("--airlight values must be within [0, 1]")
    return args


def find_images(source):
    root = source if source.is_dir() else source.parent
    candidates = source.rglob("*") if source.is_dir() else (source,)
    images = sorted(path for path in candidates if path.suffix.lower() in IMAGE_SUFFIXES and path.is_file())
    if not images:
        raise ValueError(f"No supported images found at {source}")
    keys = [path.relative_to(root).with_suffix("").as_posix().casefold() for path in images]
    if len(keys) != len(set(keys)):
        raise ValueError("Input images have conflicting relative paths after removing extensions")
    return root, images


def load_depth(path, shape, relative):
    depth = np.load(path, allow_pickle=False)
    if depth.shape != shape:
        raise ValueError(f"{path}: expected depth shape {shape}, got {depth.shape}")
    if depth.dtype.kind not in "uif" or not np.isfinite(depth).all() or depth.min() < 0:
        raise ValueError(f"{path}: depth must be real, finite and nonnegative")
    if relative and depth.max() > 1:
        raise ValueError(f"{path}: relative depth must be within [0, 1]")
    return depth.astype(np.float64, copy=False)


def srgb_to_linear(rgb):
    return np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)


def render_fog(linear, depth, strength, airlight):
    transmission = np.exp(-strength * depth)[..., None]
    mixed = linear * transmission + airlight * (1 - transmission)
    srgb = np.where(mixed <= 0.0031308, mixed * 12.92, 1.055 * mixed ** (1 / 2.4) - 0.055)
    return Image.fromarray(np.rint(np.clip(srgb, 0, 1) * 255).astype(np.uint8))


def generate(args):
    source_path = args.images.resolve()
    root, images = find_images(source_path)
    output = args.output.resolve()
    input_dirs = (source_path if source_path.is_dir() else None, args.depth_dir, args.labels)
    if any(directory is not None and output.is_relative_to(directory.resolve()) for directory in input_dirs):
        raise ValueError("Choose an output directory outside the input image, depth and label directories")
    if output.exists():
        raise FileExistsError(f"Output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    airlight = srgb_to_linear(np.asarray(args.airlight, dtype=np.float32))

    staged = output.parent / f".fog-{uuid.uuid4().hex}"
    staged.mkdir()
    try:
        for source in images:
            relative_path = source.relative_to(root)
            with Image.open(source) as image:
                if image.getexif().get(274, 1) != 1:
                    raise ValueError(f"{source}: normalize EXIF orientation and align labels/depth first")
                rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255
            linear = srgb_to_linear(rgb)
            if args.row_proxy:
                depth = np.linspace(1, 0, rgb.shape[0], dtype=np.float32)[:, None]
            else:
                depth = load_depth(args.depth_dir / relative_path.with_suffix(".npy"),
                                   rgb.shape[:2], args.depth_unit == "relative")
            for level, strength in zip(LEVEL_NAMES, args.levels):
                rendered = staged / level / "images" / relative_path.with_suffix(".png")
                rendered.parent.mkdir(parents=True, exist_ok=True)
                render_fog(linear, depth, strength, airlight).save(rendered)
                if args.labels is not None:
                    label = relative_path.with_suffix(".txt")
                    destination = staged / level / "labels" / label
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(args.labels / label, destination)
        manifest = {
            "method": "homogeneous_atmospheric_scattering_linear_srgb",
            "depth_mode": "row_proxy_preview" if args.row_proxy else args.depth_unit,
            "strength_unit": "m^-1" if args.depth_unit == "meters" else "dimensionless",
            "strengths": dict(zip(LEVEL_NAMES, args.levels)),
            "airlight_srgb": args.airlight,
            "images": str(source_path),
            "depth_dir": str(args.depth_dir.resolve()) if args.depth_dir else None,
            "labels": str(args.labels.resolve()) if args.labels else None,
            "input_images": len(images),
            "output_images": len(images) * len(LEVEL_NAMES),
        }
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        staged.rename(output)
    finally:
        if staged.is_dir() and staged.resolve() == staged and staged.parent == output.parent:
            shutil.rmtree(staged)
    print(f"Generated {manifest['output_images']} images in {output}")


if __name__ == "__main__":
    try:
        generate(parse_args())
    except (OSError, ValueError, EOFError) as error:
        raise SystemExit(f"Fog synthesis failed: {error}") from None
