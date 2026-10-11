"""
ReimagineAI - Mesh alignment

Image-to-3D models (TRELLIS.2 & co.) return furniture upright (+Y) with its
front on +Z most of the time — the same convention as the scene's objects —
but not always: sometimes the model is built facing backwards or sideways,
and the photo's viewing direction is never kept. Before a generated mesh
replaces a stand-in, we check it against the photo: place it where the
object was measured, render its silhouette from the recovered photo camera
at each quarter turn, and keep the turn that best overlaps the object's
cut-out mask. Plain numpy/OpenCV on a few thousand surface samples: ~0.1 s.
"""
from __future__ import annotations

import math
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

# Keep the canonical front unless another turn is clearly better: silhouettes
# of left-right symmetric furniture are identical front vs back.
SWITCH_MARGIN = 0.04


def fit_scale(extents: Sequence[float], dims: Sequence[float]) -> Tuple[float, float, float]:
    """
    Per-axis scale that fits a mesh (extents in its own frame) to measured
    dimensions [w, h, d] (same rule as the editor). Width and height are
    visible in the photo, so they follow the measurement — generators often
    get proportions wrong from small crops — with the stretch capped at 2x.
    Depth, which one photo can't show, keeps the model's proportions (+-25%).
    """
    ex, ey, ez = [max(1e-6, float(v)) for v in extents]
    w, h, d = [max(1e-3, float(v)) for v in dims]
    sx = w / ex
    sy = float(np.clip(h / ey, sx * 0.5, sx * 2.0))
    mean = math.sqrt(sx * sy)
    sz = float(np.clip(d / ez, mean * 0.75, mean * 1.25))
    return sx, sy, sz


def _rot_y(deg: float) -> np.ndarray:
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    # three.js rotation.y: x' = x cos + z sin, z' = -x sin + z cos
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def _quat_matrix(q: Sequence[float]) -> np.ndarray:
    x, y, z, w = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def load_points(glb_path: str, n: int = 5000) -> Optional[np.ndarray]:
    """Surface samples of a GLB in its own coordinates."""
    try:
        import trimesh

        scene = trimesh.load(glb_path, force="scene")
        mesh = scene.to_mesh() if hasattr(scene, "to_mesh") else scene.dump(concatenate=True)
        if mesh is None or len(getattr(mesh, "faces", [])) == 0:
            return None
        pts, _ = trimesh.sample.sample_surface(mesh, n, seed=0)
        return np.asarray(pts, dtype=np.float64)
    except Exception as e:
        print(f"[Align] Could not read {glb_path}: {e}")
        return None


def place_points(points: np.ndarray, obj: dict, yaw_offset: float) -> np.ndarray:
    """Mesh samples -> room coordinates, exactly as the editor places the GLB."""
    p = points @ _rot_y(yaw_offset).T                     # turn inside the object
    lo, hi = p.min(0), p.max(0)
    sx, sy, sz = fit_scale(hi - lo, obj["dimensions_m"])
    p = (p - np.array([(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2])) * np.array([sx, sy, sz])
    t = obj["transform"]
    scale = np.array(t.get("scale") or [1.0, 1.0, 1.0], dtype=float)
    p = (p * scale) @ _rot_y(float(t.get("rot_y_deg") or 0.0)).T
    return p + np.array(t["pos"], dtype=float)


def _silhouette(uv: np.ndarray, shape: Tuple[int, int]) -> np.ndarray:
    import cv2

    h, w = shape
    mask = np.zeros((h, w), np.uint8)
    inside = (uv[:, 0] >= 0) & (uv[:, 0] < w) & (uv[:, 1] >= 0) & (uv[:, 1] < h)
    pts = uv[inside].astype(np.int32)
    if len(pts) < 10:
        return mask.astype(bool)
    mask[pts[:, 1], pts[:, 0]] = 255
    k = max(3, int(round(min(h, w) / 60)) | 1)
    mask = cv2.dilate(mask, np.ones((k, k), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((k * 2 + 1, k * 2 + 1), np.uint8))
    return mask > 0


def project(camera: dict, pts: np.ndarray, size: Tuple[int, int]) -> Tuple[np.ndarray, np.ndarray]:
    """Room points -> pixels of an image of `size` through the scene camera."""
    w, h = size
    R = _quat_matrix(camera["quaternion"])  # columns: camera axes in room coords
    pc = (pts - np.asarray(camera["position"], dtype=float)) @ R
    z = -pc[:, 2]  # three.js cameras look down -Z
    ok = z > 0.05
    zs = np.where(ok, z, 1.0)
    t = math.tan(math.radians(camera["fov_deg"]) / 2)
    x_ndc = pc[:, 0] / zs / (t * camera["aspect"])
    y_ndc = pc[:, 1] / zs / t
    uv = np.stack([(x_ndc + 1) / 2 * w, (1 - y_ndc) / 2 * h], -1)
    return uv, ok


def choose_yaw_offset(
    glb_path: str,
    obj: dict,
    camera: Optional[dict],
    photo_size: Tuple[int, int],
    crop_box: Sequence[float],
    alpha: Optional[np.ndarray],
) -> Tuple[float, Dict[float, float]]:
    """
    Quarter turn (0/90/180/270) that makes the generated mesh line up with
    the object in the photo. crop_box: the crop's [x0, y0, x1, y1] in photo
    pixels; alpha: the cut-out mask in crop pixels. Returns (offset, IoUs).
    """
    if camera is None or alpha is None or not alpha.any():
        return 0.0, {}
    points = load_points(glb_path)
    if points is None:
        return 0.0, {}

    # Work at a reduced resolution: silhouettes are coarse anyway
    W, H = photo_size
    scale = min(1.0, 480.0 / max(W, H))
    size = (max(1, int(W * scale)), max(1, int(H * scale)))
    import cv2

    x0, y0, x1, y1 = [int(round(v)) for v in crop_box]
    target = np.zeros((H, W), np.uint8)
    cw, ch = max(1, x1 - x0), max(1, y1 - y0)
    target[y0:y0 + ch, x0:x0 + cw] = cv2.resize(alpha.astype(np.uint8) * 255, (cw, ch)) > 127
    target = cv2.resize(target, size, interpolation=cv2.INTER_NEAREST) > 0

    scores: Dict[float, float] = {}
    for offset in (0.0, 90.0, 180.0, 270.0):
        uv, ok = project(camera, place_points(points, obj, offset), size)
        if ok.mean() < 0.9:
            continue  # the object would sit behind the camera: bad placement
        sil = _silhouette(uv[ok], (size[1], size[0]))
        union = (sil | target).sum()
        scores[offset] = float((sil & target).sum() / union) if union else 0.0
    if not scores or 0.0 not in scores:
        return 0.0, scores
    best = max(scores, key=scores.get)
    if best != 0.0 and scores[best] - scores[0.0] < SWITCH_MARGIN:
        best = 0.0
    return best, scores
