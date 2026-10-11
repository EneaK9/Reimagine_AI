"""
ReimagineAI - Scene fidelity check (developer tool)

Builds a 3D scene from room photos with the real pipeline, then projects the
scene back onto each photo through the recovered camera — room edges, every
object's 3D box and every wall feature — and scores how well each object's
projected box overlaps its detected 2D box (IoU). If the reconstruction
matches the photo, the drawing lines up with the furniture.

Usage (from backend/):
    venv/bin/python scripts/scene_fidelity.py data/scene_images/*.jpg --out /tmp/fidelity
    venv/bin/python scripts/scene_fidelity.py --scene-json scene.json photo.jpg   # re-draw only

Needs the same API keys as the server (vision model); writes <name>.png
(overlay) and <name>.json (scene) per photo into --out.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _quat_to_matrix(q):
    x, y, z, w = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


class Projector:
    """three.js-style camera from the scene JSON -> photo pixels."""

    def __init__(self, cam: dict, size):
        self.pos = np.array(cam["position"], dtype=float)
        self.R = _quat_to_matrix(cam["quaternion"])  # columns: camera axes in world
        self.t = math.tan(math.radians(cam["fov_deg"]) / 2)
        self.aspect = cam["aspect"]
        self.W, self.H = size

    def __call__(self, pts):
        pc = (np.asarray(pts, dtype=float) - self.pos) @ self.R  # world -> camera
        z = -pc[:, 2]  # three.js cameras look down -Z
        ok = z > 0.05
        zs = np.where(ok, z, 1.0)
        x_ndc = pc[:, 0] / zs / (self.t * self.aspect)
        y_ndc = pc[:, 1] / zs / self.t
        uv = np.stack([(x_ndc + 1) / 2 * self.W, (1 - y_ndc) / 2 * self.H], -1)
        return uv, ok


def _box_corners(obj):
    w, h, d = obj["dimensions_m"]
    sx, sy, sz = obj["transform"].get("scale") or [1, 1, 1]
    w, h, d = w * sx, h * sy, d * sz
    x, y, z = obj["transform"]["pos"]
    a = math.radians(obj["transform"].get("rot_y_deg") or 0.0)
    c, s = math.cos(a), math.sin(a)
    pts = []
    for dy in (0.0, h):
        for dx, dz in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)):
            # three.js rotation.y: x' = x cos + z sin, z' = -x sin + z cos
            pts.append([x + dx * c + dz * s, y + dy, z - dx * s + dz * c])
    return np.array(pts)


def _iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def draw(scene: dict, photo: Image.Image):
    img = photo.convert("RGB").copy()
    dr = ImageDraw.Draw(img)
    cam = scene.get("camera")
    if not cam:
        return img, None
    proj = Projector(cam, img.size)
    room = scene["room"]
    w, d, h = room["width_m"], room["depth_m"], room["height_m"]

    def line(a, b, color, width=2):
        seg = np.linspace(a, b, 40)
        uv, ok = proj(seg)
        pts = [tuple(p) for p, k in zip(uv, ok) if k]
        if len(pts) > 1:
            dr.line(pts, fill=color, width=width)

    xs, zs = (-w / 2, w / 2), (-d / 2, d / 2)
    for y in (0.0, h):
        for x in xs:
            line([x, y, zs[0]], [x, y, zs[1]], (255, 70, 70))
        for z in zs:
            line([xs[0], y, z], [xs[1], y, z], (255, 70, 70))
    for x in xs:
        for z in zs:
            line([x, 0, z], [x, h, z], (255, 70, 70))

    ious = []
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]
    for obj in scene["objects"]:
        corners = _box_corners(obj)
        for i, j in edges:
            line(corners[i], corners[j], (80, 230, 120), 2)
        uv, ok = proj(corners)
        src = obj.get("source") or {}
        box, size = src.get("bbox"), src.get("img_size")
        if ok.all() and box and size:
            sx, sy = img.width / size[0], img.height / size[1]
            det = [box[0] * sx, box[1] * sy, box[2] * sx, box[3] * sy]
            got = [uv[:, 0].min(), uv[:, 1].min(), uv[:, 0].max(), uv[:, 1].max()]
            dr.rectangle(det, outline=(255, 210, 60), width=1)
            ious.append((obj.get("label") or obj["category"], _iou(det, got)))
        top = uv[ok].min(axis=0) if ok.any() else None
        if top is not None:
            dr.text((float(top[0]), max(0.0, float(top[1]) - 12)), obj["category"], fill=(80, 230, 120))

    for f in room.get("features") or []:
        if f["wall"] == "ceiling":
            continue
        a, b0, top = f["center_x_m"], f["bottom_m"], f["bottom_m"] + f["height_m"]
        half = f["width_m"] / 2
        if f["wall"] == "back":
            quad = [[a - half, b0, -d / 2], [a + half, b0, -d / 2], [a + half, top, -d / 2], [a - half, top, -d / 2]]
        elif f["wall"] == "left":
            quad = [[-w / 2, b0, a - half], [-w / 2, b0, a + half], [-w / 2, top, a + half], [-w / 2, top, a - half]]
        elif f["wall"] == "right":
            quad = [[w / 2, b0, a - half], [w / 2, b0, a + half], [w / 2, top, a + half], [w / 2, top, a - half]]
        else:
            continue
        for i in range(4):
            line(quad[i], quad[(i + 1) % 4], (90, 160, 255), 2)
    return img, ious


async def build(path: str, cache_path: str, reuse: bool):
    """Run the real pipeline; the vision-model result is cached per photo so
    geometry changes can be re-checked without paying for new API calls."""
    from app.services.scene_builder import scene_builder

    detect, refine = scene_builder.detect_room, scene_builder.refine_detection
    if reuse and os.path.exists(cache_path):
        cached = json.load(open(cache_path))

        async def fake_detect(*_a, **_k):
            return json.loads(json.dumps(cached))

        async def fake_refine(_b64, _size, first_pass):
            return first_pass

        scene_builder.detect_room, scene_builder.refine_detection = fake_detect, fake_refine
    else:
        async def saving_refine(b64, size, first_pass):
            result = await refine(b64, size, first_pass)
            with open(cache_path, "w") as fh:
                json.dump(result, fh, indent=1)
            return result

        scene_builder.refine_detection = saving_refine
    try:
        with open(path, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode()
        data, photo = await scene_builder.build_scene_from_image(b64)
    finally:
        scene_builder.detect_room, scene_builder.refine_detection = detect, refine
    return data.model_dump(), photo


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photos", nargs="+")
    ap.add_argument("--out", default="/tmp/scene_fidelity")
    ap.add_argument("--scene-json", help="draw an existing scene JSON instead of building")
    ap.add_argument("--reuse-detection", action="store_true",
                    help="reuse the cached vision-model output from a previous run (no API calls)")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    for path in args.photos:
        name = os.path.splitext(os.path.basename(path))[0]
        if args.scene_json:
            scene = json.load(open(args.scene_json))
            scene = scene.get("data", scene)
            photo = ImageOps.exif_transpose(Image.open(path))  # upright, like the pipeline
        else:
            cache = os.path.join(args.out, f"{name}.detection.json")
            scene, photo = asyncio.run(build(path, cache, args.reuse_detection))
            with open(os.path.join(args.out, f"{name}.json"), "w") as fh:
                json.dump(scene, fh, indent=1)
        img, ious = draw(scene, photo)
        img.save(os.path.join(args.out, f"{name}.png"))
        geo = scene.get("geometry") or {}
        print(f"\n{name}: {geo.get('source')} via {geo.get('model')}, "
              f"room {scene['room']['width_m']:.2f} x {scene['room']['depth_m']:.2f} x {scene['room']['height_m']:.2f} m, "
              f"{len(scene['objects'])} objects, {len(scene['room'].get('features') or [])} features")
        for label, iou in ious or []:
            print(f"   box IoU {iou:0.2f}  {label}")
        if ious:
            print(f"   mean box IoU {np.mean([i for _, i in ious]):0.2f}")


if __name__ == "__main__":
    main()
