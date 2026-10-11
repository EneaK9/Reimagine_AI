"""
ReimagineAI - Room Geometry

Measures the room in a single photo instead of guessing it:

  metric depth + focal length  ->  3D point cloud (camera frame)
  RANSAC floor plane           ->  gravity direction, camera height, pitch/roll
  Manhattan wall directions    ->  room orientation (corner shots included)
  wall / ceiling planes        ->  room box in meters
  per-object point sets        ->  position, footprint, height and facing
  rays through feature boxes   ->  windows/doors/art placed on the right wall

Everything here is plain numpy/OpenCV so it runs on the CPU server.

Coordinate conventions (shared with the scene JSON and the three.js editor):
  camera frame (OpenCV): x right, y down, z forward.
  room frame: y up, floor at y = 0, room centered on x = z = 0. The wall the
  camera faces ("back") is at z = -depth/2; the camera stands on the +z side.
  rot_y_deg = 0 means an object's front faces +z (toward the camera side).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

# Horizontal FOV used when the photo carries no calibration signal. It is the
# training camera of Depth Anything V2 metric (Hypersim, ~60 deg), so the
# network's metric scale stays self-consistent with the back-projection.
DEFAULT_HFOV_DEG = 60.0
WORK_WIDTH = 320  # analysis resolution; room-scale geometry is smooth

FLOOR, WALL, CEILING = 1, 2, 3
WALL_NAMES = ("back", "left", "right")


# ---------------------------------------------------------------- camera

@dataclass
class Camera:
    """Pinhole intrinsics for an image of size (width, height)."""
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float
    source: str = "default"  # exif | manhattan | default

    @classmethod
    def from_hfov(cls, width: int, height: int, hfov_deg: float, source: str = "default") -> "Camera":
        f = (width / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)
        return cls(width, height, f, f, width / 2.0, height / 2.0, source)

    @property
    def hfov_deg(self) -> float:
        return math.degrees(2.0 * math.atan(self.width / (2.0 * self.fx)))

    @property
    def vfov_deg(self) -> float:
        return math.degrees(2.0 * math.atan(self.height / (2.0 * self.fy)))

    def rays(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Camera-frame ray directions (z = 1) through pixel coordinates."""
        u = np.asarray(u, dtype=np.float64)
        v = np.asarray(v, dtype=np.float64)
        return np.stack([(u - self.cx) / self.fx, (v - self.cy) / self.fy, np.ones_like(u)], -1)


def hfov_from_exif(image) -> Optional[float]:
    """Horizontal FOV from the 35mm-equivalent focal length, when present."""
    try:
        exif = image.getexif()
        f35 = exif.get_ifd(0x8769).get(0xA405) or exif.get(0xA405)  # FocalLengthIn35mmFilm
        if not f35:
            return None
        w, h = image.size
        # 35mm-equivalent focal is defined on the 36x24mm frame diagonal
        dfov = 2.0 * math.atan(math.hypot(36.0, 24.0) / (2.0 * float(f35)))
        hfov = math.degrees(2.0 * math.atan(math.tan(dfov / 2.0) * w / math.hypot(w, h)))
        return hfov if 25.0 <= hfov <= 120.0 else None
    except Exception:
        return None


# ---------------------------------------------------------------- low-level helpers

def backproject(depth: np.ndarray, cam: Camera) -> np.ndarray:
    """(H, W) planar depth in meters -> (H, W, 3) camera-frame points."""
    h, w = depth.shape
    u, v = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    rays = cam.rays(u, v)
    return rays * depth[..., None]


def point_normals(points: np.ndarray) -> np.ndarray:
    """Per-pixel normals from a point map, oriented toward the camera."""
    dx = np.zeros_like(points)
    dy = np.zeros_like(points)
    dx[:, 1:-1] = points[:, 2:] - points[:, :-2]
    dy[1:-1] = points[2:] - points[:-2]
    n = np.cross(dx, dy)
    n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9
    flip = (n * points).sum(-1) > 0
    n[flip] *= -1.0
    return n


def _smooth_depth(depth: np.ndarray) -> np.ndarray:
    import cv2

    return cv2.bilateralFilter(depth.astype(np.float32), 5, 0.1, 3)


def _fit_plane_svd(pts: np.ndarray) -> Tuple[np.ndarray, float]:
    c = pts.mean(0)
    _, _, vt = np.linalg.svd(pts - c, full_matrices=False)
    n = vt[2]
    return n, float(-n @ c)


def _ransac_floor(
    points: np.ndarray,
    normals: np.ndarray,
    candidates: np.ndarray,
    rng: np.random.Generator,
    iters: int = 200,
    thresh: float = 0.04,
) -> Optional[Tuple[np.ndarray, float, float]]:
    """
    Floor plane n.p + d = 0 in camera coordinates, n pointing up (toward the
    camera), d = camera height. Returns (n, d, inlier_fraction) or None.
    """
    pts = points[candidates & (normals[..., 1] < -0.6)]
    if len(pts) < 150:
        return None
    if len(pts) > 12000:
        pts = pts[rng.choice(len(pts), 12000, replace=False)]
    best_count, best = 0, None
    for _ in range(iters):
        s = pts[rng.choice(len(pts), 3, replace=False)]
        n = np.cross(s[1] - s[0], s[2] - s[0])
        norm = np.linalg.norm(n)
        if norm < 1e-9:
            continue
        n /= norm
        if n[1] > 0:
            n = -n
        if n[1] > -0.55:  # floor normal must point roughly "up" in the image
            continue
        d = float(-n @ s[0])
        if d < 0.3:  # the camera stands above the floor
            continue
        count = int((np.abs(pts @ n + d) < thresh).sum())
        if count > best_count:
            best_count, best = count, (n, d)
    if best is None:
        return None
    n, d = best
    inliers = pts[np.abs(pts @ n + d) < thresh]
    n, d = _fit_plane_svd(inliers)
    if n[1] > 0:
        n, d = -n, -d
    return n, d, best_count / len(pts)


def _manhattan(normals_room0: np.ndarray, mask: np.ndarray) -> Tuple[float, float, int]:
    """
    Dominant wall orientation (radians, in (-45, 45] deg) of vertical surfaces
    in a gravity-aligned frame, plus its concentration R (0..1) and support.
    """
    n = normals_room0[mask]
    vertical = np.abs(n[:, 1]) < 0.25
    n = n[vertical]
    if len(n) < 300:
        return 0.0, 0.0, len(n)
    theta = np.arctan2(n[:, 2], n[:, 0])
    z = np.exp(4j * theta).mean()
    return float(np.angle(z) / 4.0), float(np.abs(z)), len(n)


def _gravity_frame(n_up: np.ndarray, yaw: float = 0.0) -> np.ndarray:
    """Rows = room axes (X right, Y up, Z toward camera) in camera coords."""
    fwd = np.array([0.0, 0.0, 1.0])
    fh = fwd - (fwd @ n_up) * n_up
    fh /= np.linalg.norm(fh) + 1e-12
    z0 = -fh
    x0 = np.cross(n_up, z0)
    c, s = math.cos(yaw), math.sin(yaw)
    x1 = c * x0 + s * z0
    z1 = -s * x0 + c * z0
    return np.stack([x1, n_up, z1])


def _extreme_peak(values: np.ndarray, min_support: int, side: str, bin_m: float = 0.05) -> Optional[float]:
    """
    Coordinate of the farthest well-supported plane along an axis. "Well
    supported" is relative to the strongest plane: small far-away patches
    (a room seen through an open door, a reflection) must not win.
    """
    if len(values) < min_support:
        return None
    lo, hi = np.percentile(values, [0.5, 99.5])
    if hi - lo < bin_m:
        return float(np.median(values))
    bins = max(4, int(math.ceil((hi - lo) / bin_m)))
    hist, edges = np.histogram(values, bins=bins, range=(lo, hi))
    hist = np.convolve(hist, [1, 2, 1], mode="same") / 4.0
    peaks = []
    for i in range(len(hist)):
        left = hist[i - 1] if i > 0 else 0
        right = hist[i + 1] if i + 1 < len(hist) else 0
        if hist[i] > 0 and hist[i] >= left and hist[i] >= right:
            center = (edges[i] + edges[i + 1]) / 2.0
            support = int((np.abs(values - center) < bin_m * 1.6).sum())
            peaks.append((center, support))
    if not peaks:
        return None
    strongest = max(s for _, s in peaks)
    need = max(min_support, int(strongest * 0.3))
    good = [c for c, s in peaks if s >= need]
    if not good:
        return None
    center = min(good) if side == "min" else max(good)
    return float(np.median(values[np.abs(values - center) < bin_m * 1.6]))


# ---------------------------------------------------------------- results

@dataclass
class RoomBox:
    x_min: float
    x_max: float
    z_min: float  # back wall
    z_max: float  # front wall (behind the camera, never observed)
    height: float
    observed: Dict[str, bool] = field(default_factory=dict)

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def depth(self) -> float:
        return self.z_max - self.z_min


@dataclass
class ObjectEstimate:
    center: Tuple[float, float, float]  # x, y(base), z in room coords
    dims: Tuple[float, float, float]    # width, height, depth (object frame)
    rot_y_deg: float
    confidence: float
    against_wall: Optional[str] = None
    method: str = "depth"
    visible_width: Optional[float] = None   # measured, before priors (scale cues)
    visible_height: Optional[float] = None
    mask: Optional[np.ndarray] = None       # object pixels at analysis resolution

    def scaled(self, s: float) -> "ObjectEstimate":
        return ObjectEstimate(
            center=tuple(v * s for v in self.center),
            dims=tuple(round(v * s, 3) for v in self.dims),
            rot_y_deg=self.rot_y_deg,
            confidence=self.confidence,
            against_wall=self.against_wall,
            method=self.method,
            visible_width=self.visible_width * s if self.visible_width else None,
            visible_height=self.visible_height * s if self.visible_height else None,
            mask=self.mask,
        )


@dataclass
class FeatureEstimate:
    wall: str
    center_along: float  # offset along the wall from its center (scene JSON center_x_m)
    width: float
    bottom: float
    height: float
    center_z: float = 0.0  # ceiling features only


@dataclass
class RoomGeometry:
    camera: Camera                 # intrinsics at the analysis resolution
    R: np.ndarray                  # room_from_camera rotation (3x3)
    t: np.ndarray                  # camera position in room coords
    box: RoomBox
    points: np.ndarray             # (H, W, 3) room coords
    normals: np.ndarray            # (H, W, 3) room coords
    valid: np.ndarray              # (H, W) bool
    structure: np.ndarray          # (H, W) uint8: FLOOR / WALL / CEILING / 0
    quality: Dict[str, float] = field(default_factory=dict)
    edges: Optional[np.ndarray] = None  # (H, W) bool: depth discontinuities (object outlines)

    # ---- projection helpers (u, v in normalized [0, 1] image coords) ----

    def ray(self, u: float, v: float) -> np.ndarray:
        """Unit ray direction in room coords through normalized pixel (u, v)."""
        d = self.camera.rays(np.array(u * self.camera.width), np.array(v * self.camera.height))
        d = self.R @ d
        return d / np.linalg.norm(d)

    def project(self, pts_room: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Room points -> normalized image coords (N, 2) and camera depth (N,)."""
        pc = (np.asarray(pts_room, dtype=np.float64) - self.t) @ self.R  # R^T (p - t)
        z = pc[:, 2]
        safe = np.where(np.abs(z) < 1e-6, 1e-6, z)
        u = (pc[:, 0] / safe * self.camera.fx + self.camera.cx) / self.camera.width
        v = (pc[:, 1] / safe * self.camera.fy + self.camera.cy) / self.camera.height
        return np.stack([u, v], -1), z

    def floor_hit(self, u: float, v: float) -> Optional[np.ndarray]:
        """Where the ray through (u, v) meets the floor, if it does."""
        d = self.ray(u, v)
        if d[1] >= -1e-3:
            return None
        s = -self.t[1] / d[1]
        return self.t + s * d if s > 0 else None

    def wall_planes(self) -> Dict[str, Tuple[np.ndarray, float]]:
        """Inward-facing wall planes (n.p + d = 0) of the room box."""
        b = self.box
        return {
            "back": (np.array([0.0, 0.0, 1.0]), -b.z_min),
            "left": (np.array([1.0, 0.0, 0.0]), -b.x_min),
            "right": (np.array([-1.0, 0.0, 0.0]), b.x_max),
            "front": (np.array([0.0, 0.0, -1.0]), b.z_max),
        }

    def editor_camera(self) -> Dict[str, object]:
        """The photo's viewpoint for three.js (camera looks down its local -Z)."""
        right, down, fwd = self.R[:, 0], self.R[:, 1], self.R[:, 2]
        rot = np.stack([right, -down, -fwd], axis=1)  # columns = three.js local axes
        target = self.t + fwd * max(1.5, min(4.0, self.box.depth * 0.6))
        return {
            "position": [round(float(v), 4) for v in self.t],
            "quaternion": [round(float(v), 6) for v in _quat_from_matrix(rot)],
            "target": [round(float(v), 4) for v in target],
            "fov_deg": round(self.camera.vfov_deg, 3),
            "aspect": round(self.camera.width / self.camera.height, 5),
            "fov_source": self.camera.source,
        }


def _quat_from_matrix(m: np.ndarray) -> Tuple[float, float, float, float]:
    """Rotation matrix -> quaternion (x, y, z, w), three.js order."""
    tr = m[0, 0] + m[1, 1] + m[2, 2]
    if tr > 0:
        s = 0.5 / math.sqrt(tr + 1.0)
        w, x = 0.25 / s, (m[2, 1] - m[1, 2]) * s
        y, z = (m[0, 2] - m[2, 0]) * s, (m[1, 0] - m[0, 1]) * s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = 2.0 * math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2])
        w, x = (m[2, 1] - m[1, 2]) / s, 0.25 * s
        y, z = (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = 2.0 * math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2])
        w, x = (m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s
        y, z = 0.25 * s, (m[1, 2] + m[2, 1]) / s
    else:
        s = 2.0 * math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1])
        w, x = (m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s
        y, z = (m[1, 2] + m[2, 1]) / s, 0.25 * s
    q = np.array([x, y, z, w])
    return tuple(q / np.linalg.norm(q))


# ---------------------------------------------------------------- analysis

def _resize_depth(depth: np.ndarray) -> np.ndarray:
    import cv2

    h, w = depth.shape
    if w <= WORK_WIDTH:
        return depth.astype(np.float32)
    nh = max(8, int(round(h * WORK_WIDTH / w)))
    return cv2.resize(depth.astype(np.float32), (WORK_WIDTH, nh), interpolation=cv2.INTER_AREA)


def _box_mask(shape: Tuple[int, int], boxes: Sequence[Sequence[float]], pad: float = 0.0) -> np.ndarray:
    """Mask of normalized [x0, y0, x1, y1] boxes on an (H, W) grid."""
    h, w = shape
    mask = np.zeros((h, w), bool)
    for b in boxes:
        try:
            x0, y0, x1, y1 = [float(v) for v in b]
        except (TypeError, ValueError):
            continue
        px, py = (x1 - x0) * pad, (y1 - y0) * pad
        c0, c1 = int(max(0, (x0 - px) * w)), int(min(w, math.ceil((x1 + px) * w)))
        r0, r1 = int(max(0, (y0 - py) * h)), int(min(h, math.ceil((y1 + py) * h)))
        mask[r0:r1, c0:c1] = True
    return mask


def _calibrate(
    depth: np.ndarray,
    valid: np.ndarray,
    floor_region: np.ndarray,
    rng: np.random.Generator,
    around: Optional[float] = None,
) -> Tuple[Optional[float], Dict[str, float]]:
    """
    Self-calibrate the focal length: the right FOV is the one that makes the
    back-projected room most "Manhattan" (walls square to each other and to
    the floor). Only well-conditioned for two-point (angled) views; a camera
    squarely facing a wall leaves the focal length unobservable.

    around: a model's FOV estimate to refine locally (+-8 deg) instead of a
    full search; the estimate is kept unless the room gets clearly squarer.
    """
    h, w = depth.shape

    def score(hfov: float) -> Tuple[float, float]:
        cam = Camera.from_hfov(w, h, hfov)
        pts = backproject(depth, cam)
        nrm = point_normals(pts)
        fl = _ransac_floor(pts, nrm, floor_region & valid, rng, iters=120)
        if fl is None:
            return 0.0, 0.0
        frame = _gravity_frame(fl[0])
        yaw, conc, _ = _manhattan(nrm @ frame.T, valid)
        return conc, math.degrees(yaw)

    if around is not None:
        base = score(around)
        # Zoomed or ultra-wide shots may sit outside the usual lens range:
        # search around the estimate itself rather than a fixed window
        local = {float(f): score(float(f)) for f in np.arange(around - 8.0, around + 8.1, 2.0) if 15.0 <= f <= 140.0}
        local[float(around)] = base
        best = max(local, key=lambda f: local[f][0])
        conc, yaw = local[best]
        info = {"calib_hint_hfov": around, "calib_peak_hfov": float(best), "calib_conc": conc,
                "calib_gain": conc - base[0], "calib_yaw": yaw}
        if abs(yaw) >= 12.0 and conc > 0.35 and conc - base[0] > 0.01:
            return float(best), info
        return around, info

    scores = {float(f): score(float(f)) for f in range(40, 91, 5)}
    coarse_best = max(scores, key=lambda f: scores[f][0])
    for f in (coarse_best - 2.0, coarse_best + 2.0):
        if 38.0 <= f <= 92.0:
            scores[f] = score(f)
    best = max(scores, key=lambda f: scores[f][0])
    conc, yaw = scores[best]

    # A real optimum is a peak: clearly better than FOVs ~10 deg away on both
    # sides. Frontal (one-point) views give a flat or monotonic curve instead.
    left = [c for f, (c, _) in scores.items() if f <= best - 8.0]
    right = [c for f, (c, _) in scores.items() if f >= best + 8.0]
    drop = min(conc - max(left), conc - max(right)) if left and right else 0.0
    angled = abs(yaw) >= 12.0  # |yaw| <= 45 by construction; ~0 = facing a wall
    info = {"calib_peak_hfov": best, "calib_conc": conc, "calib_yaw": yaw, "calib_drop": drop}
    if angled and conc > 0.35 and drop > 0.015:
        return best, info
    return None, info


def analyze_room(
    depth: np.ndarray,
    image_size: Tuple[int, int],
    fov_hint: Optional[float] = None,
    fov_source: str = "exif",
    exclude_boxes: Sequence[Sequence[float]] = (),
    floor_hint_box: Optional[Sequence[float]] = None,
    estimate: Optional[Dict[str, float]] = None,
    seed: int = 0,
) -> Optional[RoomGeometry]:
    """
    Recover camera + room box from a metric depth map.

    depth: planar depth in meters (any resolution; resized internally).
    image_size: (width, height) of the photo the depth map was computed on.
    fov_hint / fov_source: horizontal FOV from EXIF (trusted as is) or from
        the depth model (refined against the room's right angles).
    exclude_boxes: normalized boxes whose depth is unreliable for the room
        shell (windows show the outside, mirrors show a reflected room,
        open doors show the next room).
    floor_hint_box: normalized box the vision model saw as clean floor.
    estimate: the vision model's {"width_m", "depth_m", "height_m"} guess,
        used only for walls the photo does not show.
    Returns None when no floor is visible (caller falls back to layout-only).
    """
    rng = np.random.default_rng(seed)
    d = _smooth_depth(_resize_depth(depth))
    h, w = d.shape
    valid = np.isfinite(d) & (d > 0.2) & (d < 20.0)
    unreliable = _box_mask((h, w), exclude_boxes)

    floor_region = np.zeros((h, w), bool)
    floor_region[int(h * 0.5):] = True
    if floor_hint_box is not None:
        floor_region |= _box_mask((h, w), [floor_hint_box])
    floor_region &= ~unreliable

    # ---- focal length: EXIF > model estimate (+ Manhattan refinement) >
    # Manhattan self-calibration > default
    info: Dict[str, float] = {}
    if fov_hint and fov_source == "exif":
        cam = Camera.from_hfov(w, h, fov_hint, "exif")
    elif fov_hint:
        hfov, info = _calibrate(d, valid & ~unreliable, floor_region, rng, around=float(fov_hint))
        source = fov_source if abs(hfov - fov_hint) < 0.5 else f"{fov_source}+manhattan"
        cam = Camera.from_hfov(w, h, hfov, source)
    else:
        hfov, info = _calibrate(d, valid & ~unreliable, floor_region, rng)
        cam = Camera.from_hfov(w, h, hfov, "manhattan") if hfov else Camera.from_hfov(w, h, DEFAULT_HFOV_DEG)

    pts_c = backproject(d, cam)
    nrm_c = point_normals(pts_c)
    floor = _ransac_floor(pts_c, nrm_c, floor_region & valid, rng, iters=300)
    if floor is None:
        print("[Geometry] No floor plane found — falling back to layout-only placement")
        return None
    n_up, cam_h, floor_frac = floor
    if not (0.4 <= cam_h <= 3.2):
        print(f"[Geometry] Implausible camera height {cam_h:.2f} m — ignoring geometry")
        return None

    # ---- gravity-aligned, wall-aligned room frame
    frame0 = _gravity_frame(n_up)
    yaw, conc, _ = _manhattan(nrm_c @ frame0.T, valid & ~unreliable)
    # Rows = room axes in camera coords, so p_room = R @ p_cam + t and the
    # columns of R are the camera axes expressed in room coords.
    R = _gravity_frame(n_up, yaw)
    t = np.array([0.0, cam_h, 0.0])
    pts = pts_c @ R.T + t
    nrm = nrm_c @ R.T

    # ---- structure: floor, walls, ceiling
    structure = np.zeros((h, w), np.uint8)
    floor_px = valid & (np.abs(pts[..., 1]) < 0.05) & (nrm[..., 1] > 0.8)
    structure[floor_px] = FLOOR

    shell_ok = valid & ~unreliable
    support = max(60, int(shell_ok.sum() * 0.006))
    walls: Dict[str, Optional[float]] = {}
    for name, axis, sign, side in (("back", 2, 1.0, "min"), ("left", 0, 1.0, "min"), ("right", 0, -1.0, "max")):
        cand = shell_ok & (nrm[..., axis] * sign > 0.8) & (pts[..., 1] > 0.05)
        coord = pts[..., axis][cand]
        pos = _extreme_peak(coord, support, side)
        if pos is not None:
            near = cand & (np.abs(pts[..., axis] - pos) < 0.08)
            ys = pts[..., 1][near]
            # A real wall spans a good part of the room height; furniture fronts don't
            if near.sum() < support or len(ys) == 0 or np.ptp(ys) < 0.6:
                pos = None
            else:
                structure[near] = WALL
        walls[name] = pos
    # Walls must enclose the camera
    if walls["back"] is not None and walls["back"] > -0.3:
        walls["back"] = None
    if walls["left"] is not None and walls["left"] > -0.15:
        walls["left"] = None
    if walls["right"] is not None and walls["right"] < 0.15:
        walls["right"] = None

    ceil_cand = shell_ok & (nrm[..., 1] < -0.8) & (pts[..., 1] > cam_h + 0.2)
    ceiling = _extreme_peak(pts[..., 1][ceil_cand], support, "max")
    if ceiling is not None:
        structure[ceil_cand & (np.abs(pts[..., 1] - ceiling) < 0.08)] = CEILING

    # ---- room box: measured walls first, the model's estimate for the rest
    est = estimate or {}
    content = valid & ~unreliable & (structure != CEILING) & (pts[..., 1] < 2.6)
    xs, zs = pts[..., 0][content], pts[..., 2][content]
    if len(xs) < 50:
        return None
    x_lo, x_hi = np.percentile(xs, [1, 99])
    z_lo = np.percentile(zs, 1)
    est_w = float(est.get("width_m") or 0) or None
    est_d = float(est.get("depth_m") or 0) or None
    est_h = float(est.get("height_m") or 0) or None

    x_min = walls["left"] if walls["left"] is not None else float(x_lo) - 0.15
    x_max = walls["right"] if walls["right"] is not None else float(x_hi) + 0.15
    if est_w and x_max - x_min < est_w:
        # Stretch toward the side(s) the photo does not show
        missing = est_w - (x_max - x_min)
        if walls["left"] is None and walls["right"] is None:
            x_min, x_max = x_min - missing / 2, x_max + missing / 2
        elif walls["left"] is None:
            x_min -= missing
        elif walls["right"] is None:
            x_max += missing
    # The photo was taken from inside the room: unseen walls must enclose the
    # camera (x = z = 0 here), or wall features get cast onto a phantom wall
    # between the camera and the room.
    if walls["left"] is None:
        x_min = min(x_min, -0.4)
    if walls["right"] is None:
        x_max = max(x_max, 0.4)
    z_min = walls["back"] if walls["back"] is not None else float(z_lo) - 0.15
    # Front wall sits behind the camera; never visible
    z_max = 0.6
    if est_d:
        z_max = min(2.5, max(0.45, z_min + est_d))
    height = ceiling if ceiling is not None else float(np.clip(est_h or 2.6, 2.3, 3.2))
    top = np.percentile(pts[..., 1][content], 99.5) if content.any() else 2.2
    height = float(max(height, min(top + 0.05, 3.6), 2.2))

    # Room centered on the origin
    shift = np.array([-(x_min + x_max) / 2.0, 0.0, -(z_min + z_max) / 2.0])
    pts = pts + shift
    t = t + shift
    box = RoomBox(
        x_min=x_min + shift[0], x_max=x_max + shift[0],
        z_min=z_min + shift[2], z_max=z_max + shift[2],
        height=height,
        observed={
            "back": walls["back"] is not None,
            "left": walls["left"] is not None,
            "right": walls["right"] is not None,
            "ceiling": ceiling is not None,
        },
    )

    pitch = math.degrees(math.asin(float(np.clip(-n_up[2], -1, 1))))
    roll = math.degrees(math.atan2(float(n_up[0]), float(-n_up[1])))
    quality = {
        "camera_height_m": round(float(cam_h), 3),
        "pitch_deg": round(pitch, 2),
        "roll_deg": round(roll, 2),
        "wall_yaw_deg": round(math.degrees(yaw), 2),
        "manhattan": round(conc, 3),
        "floor_inliers": round(float(floor_frac), 3),
        "hfov_deg": round(cam.hfov_deg, 2),
        **{k: round(float(v), 3) for k, v in info.items()},
    }
    print(
        f"[Geometry] camera h={cam_h:.2f}m pitch={pitch:.1f} roll={roll:.1f} "
        f"hfov={cam.hfov_deg:.0f} ({cam.source}), wall yaw={math.degrees(yaw):.1f}, "
        f"room {box.width:.2f}x{box.depth:.2f}x{box.height:.2f}m, walls seen: "
        f"{[k for k, v in box.observed.items() if v]}"
    )
    # Depth jumps separate an object from whatever is behind it
    gy, gx = np.gradient(d)
    edges = (np.hypot(gx, gy) / np.maximum(d, 0.3)) > 0.05
    return RoomGeometry(
        camera=cam, R=R, t=t, box=box, points=pts, normals=nrm,
        valid=valid, structure=structure, quality=quality, edges=edges,
    )


def rescale(geom: RoomGeometry, s: float) -> None:
    """Uniformly rescale the reconstruction (metric-scale correction)."""
    if abs(s - 1.0) < 1e-3:
        return
    geom.points = geom.points * s
    geom.t = geom.t * s
    b = geom.box
    b.x_min, b.x_max, b.z_min, b.z_max = b.x_min * s, b.x_max * s, b.z_min * s, b.z_max * s
    b.height = float(np.clip(b.height * s, 2.2, 3.8))
    geom.quality["scale_correction"] = round(s, 3)


# ---------------------------------------------------------------- objects

def _facing_vector(facing: Optional[str], geom: RoomGeometry, center: np.ndarray) -> Optional[np.ndarray]:
    """Camera-relative facing hint ("camera", "away", "left", "right") -> room XZ vector."""
    if not isinstance(facing, str) or not facing.strip():
        return None
    fwd = geom.R[:, 2].copy()
    fwd[1] = 0.0
    fwd /= np.linalg.norm(fwd) + 1e-9
    right = np.array([-fwd[2], 0.0, fwd[0]])
    to_cam = geom.t - center
    to_cam[1] = 0.0
    to_cam /= np.linalg.norm(to_cam) + 1e-9
    return {
        "camera": to_cam, "toward_camera": to_cam, "front": to_cam,
        "away": -to_cam, "away_from_camera": -to_cam, "back": -to_cam,
        "left": -right, "right": right,
    }.get(facing.strip().lower())


def _snap_yaw(vec: np.ndarray) -> float:
    """Facing vector -> yaw snapped to the wall axes (0 = faces +z)."""
    deg = math.degrees(math.atan2(vec[0], vec[2]))
    return float((round(deg / 90.0) * 90.0) % 360.0)


def place_object(
    geom: RoomGeometry,
    box: Sequence[float],
    prior_dims: Sequence[float],
    facing: Optional[str] = None,
    wall_hugger: bool = False,
    flat: bool = False,
    occupied: Optional[np.ndarray] = None,
    stackable: bool = True,
) -> Optional[ObjectEstimate]:
    """
    Measure one object from the depth points inside its normalized bbox.

    prior_dims: expected [width, height, depth] (catalog x detected width),
        used for the parts the photo cannot see (the hidden back, cut-off sides).
    flat: rugs and other floor coverings — measured from floor rays only.
    occupied: pixels already claimed by nearer objects (optional).
    stackable: may stand on other furniture (lamps, plants). Beds,
        nightstands, sofas... always stand on the floor, even when their
        lowest visible point is a drawer above an open shelf.
    """
    h, w = geom.valid.shape
    x0, y0, x1, y1 = [float(v) for v in box]
    if x1 - x0 < 0.01 or y1 - y0 < 0.01:
        return None
    pw, ph, pd = [max(0.05, float(v)) for v in prior_dims]
    truncated_l, truncated_r = x0 < 0.01, x1 > 0.99
    truncated_b = y1 > 0.99

    if flat:
        return _place_flat(geom, (x0, y0, x1, y1), (pw, ph, pd), truncated_b)

    # Shrink the box a little: its borders are mostly background
    sx, sy = (x1 - x0) * 0.04, (y1 - y0) * 0.03
    mask = _box_mask((h, w), [(x0 + sx, y0 + sy, x1 - sx, y1 - sy)])
    # Drop structure, including floor pixels whose noisy normals kept them
    # out of the floor label (they would stretch footprints toward the camera)
    mask &= geom.valid & (geom.structure == 0) & (geom.points[..., 1] > 0.04)
    if occupied is not None:
        mask &= ~occupied
    pts = geom.points[mask]
    if len(pts) < 25:
        return (_place_by_rays(geom, (x0, y0, x1, y1), (pw, ph, pd), facing, wall_hugger, truncated_b)
                or _place_by_center_depth(geom, (x0, y0, x1, y1), (pw, ph, pd)))

    # Foreground cluster: distance band around the object's floor-contact region
    dist = np.linalg.norm(pts - geom.t, axis=1)
    rows = np.nonzero(mask)[0]
    bottom = rows >= np.percentile(rows, 55)
    anchor = np.median(dist[bottom]) if bottom.sum() >= 10 else np.median(dist)
    span = max(pw, pd) * 1.2 + 0.25
    keep = (dist > anchor - span * 0.45) & (dist < anchor + span)
    pts = pts[keep]
    if len(pts) < 20:
        return (_place_by_rays(geom, (x0, y0, x1, y1), (pw, ph, pd), facing, wall_hugger, truncated_b)
                or _place_by_center_depth(geom, (x0, y0, x1, y1), (pw, ph, pd)))
    obj_mask = np.zeros((h, w), bool)
    obj_mask[mask] = keep
    # Keep the one blob that fills the box's core: depth edges cut it free
    # from the wall or furniture behind it that the box also covers.
    obj_mask = _core_component(obj_mask, geom.edges, (x0, y0, x1, y1))
    pts = geom.points[obj_mask]
    if len(pts) < 20:
        return (_place_by_rays(geom, (x0, y0, x1, y1), (pw, ph, pd), facing, wall_hugger, truncated_b)
                or _place_by_center_depth(geom, (x0, y0, x1, y1), (pw, ph, pd)))

    y_base = float(np.percentile(pts[:, 1], 2))
    on_floor = y_base < 0.18 or not stackable
    # Footprint from the lower part (what stands on the floor); the top of
    # the box often also covers wall behind the object.
    low = pts[pts[:, 1] < y_base + 0.6]
    if len(low) < max(15, int(0.2 * len(pts))):
        low = pts
    # Trim the soft "flying pixels" monocular depth leaves at object edges
    lo = np.percentile(low, 3, axis=0)
    hi = np.percentile(low, 97, axis=0)
    # Height from the column above that footprint only
    column = pts[(pts[:, 0] > lo[0] - 0.05) & (pts[:, 0] < hi[0] + 0.05)
                 & (pts[:, 2] > lo[2] - 0.05) & (pts[:, 2] < hi[2] + 0.05)]
    y_top = float(np.percentile((column if len(column) >= 10 else pts)[:, 1], 97))
    if on_floor:
        y_base = 0.0
    height = max(0.05, y_top - y_base)

    center = np.array([(lo[0] + hi[0]) / 2.0, y_base, (lo[2] + hi[2]) / 2.0])
    ext_x, ext_z = hi[0] - lo[0], hi[2] - lo[2]

    # ---- facing: back against a nearby wall, else the model's hint, else the camera
    b = geom.box
    gaps = {
        "back": lo[2] - b.z_min,
        "left": lo[0] - b.x_min,
        "right": b.x_max - hi[0],
    }
    wall, gap = min(gaps.items(), key=lambda kv: kv[1])
    reach = max(0.35, pd * 0.8) if wall_hugger else 0.3
    against = wall if gap < reach and b.observed.get(wall, True) else None
    if against is None and wall_hugger and gap < max(1.0, pd * 1.5):
        against = wall
    hint = _facing_vector(facing, geom, center)
    if against == "back":
        yaw = 0.0
    elif against == "left":
        yaw = 90.0
    elif against == "right":
        yaw = 270.0
    elif hint is not None:
        yaw = _snap_yaw(hint)
    else:
        to_cam = geom.t - center
        yaw = _snap_yaw(np.array([to_cam[0], 0.0, to_cam[2]]))

    # ---- footprint in the object's own frame
    along_x = yaw % 180.0 == 0.0  # width runs along room x
    vis_w, vis_d = (ext_x, ext_z) if along_x else (ext_z, ext_x)
    width = vis_w
    if truncated_l or truncated_r or vis_w < pw * 0.55:
        width = max(vis_w, pw)  # cut off by the frame or hidden: trust the prior
    width = float(np.clip(width, pw * 0.5, pw * 1.8))
    # The back half of an object is usually hidden: never shallower than the prior
    depth = float(np.clip(max(vis_d, pd * 0.9), pd * 0.6, pd * 1.6))
    height = float(np.clip(height, ph * 0.5, ph * 1.6)) if on_floor else float(np.clip(height, 0.05, ph * 1.8))

    # Grow the hidden part away from the camera
    to_cam = geom.t - center
    if along_x:
        grow = depth - vis_d
        if grow > 0:
            center[2] -= math.copysign(grow / 2.0, to_cam[2])
    else:
        grow = depth - vis_d
        if grow > 0:
            center[0] -= math.copysign(grow / 2.0, to_cam[0])

    # Flush against the wall it backs onto
    half_d = depth / 2.0
    if against == "back":
        center[2] = b.z_min + half_d + 0.02
    elif against == "left":
        center[0] = b.x_min + half_d + 0.02
    elif against == "right":
        center[0] = b.x_max - half_d - 0.02

    n_ratio = min(1.0, len(pts) / 400.0)
    conf = 0.35 + 0.5 * n_ratio + (0.15 if against else 0.0)
    top_cut = y0 < 0.01  # the top is outside the photo: height is a lower bound
    return ObjectEstimate(
        center=(float(center[0]), float(y_base), float(center[2])),
        dims=(round(width, 3), round(height, 3), round(depth, 3)),
        rot_y_deg=yaw,
        confidence=round(min(1.0, conf), 3),
        against_wall=against,
        method="depth",
        visible_width=None if (truncated_l or truncated_r) else float(vis_w),
        visible_height=None if (top_cut or not on_floor) else float(y_top - y_base),
        mask=obj_mask,
    )


def _place_by_rays(geom, box, prior, facing, wall_hugger, truncated_b) -> Optional[ObjectEstimate]:
    """
    Fallback for objects with too few depth points (thin legs, dark or
    reflective surfaces): the bottom edge of the bbox touches the floor, so
    rays through its corners give the front edge on the floor plane.
    """
    x0, y0, x1, y1 = box
    pw, ph, pd = prior
    if truncated_b:
        return None
    left, right = geom.floor_hit(x0, y1), geom.floor_hit(x1, y1)
    mid = geom.floor_hit((x0 + x1) / 2.0, y1)
    if left is None or right is None or mid is None:
        return None
    width = float(np.clip(np.linalg.norm(right - left), pw * 0.5, pw * 1.8))
    to_cam = geom.t - mid
    to_cam[1] = 0.0
    to_cam /= np.linalg.norm(to_cam) + 1e-9
    center = mid - to_cam * (pd / 2.0)
    hint = _facing_vector(facing, geom, center)
    yaw = _snap_yaw(hint if hint is not None else to_cam)
    return ObjectEstimate(
        center=(float(center[0]), 0.0, float(center[2])),
        dims=(round(width, 3), round(ph, 3), round(pd, 3)),
        rot_y_deg=yaw,
        confidence=0.35,
        method="rays",
    )


def _core_component(mask: np.ndarray, edges: Optional[np.ndarray], box) -> np.ndarray:
    """The connected region (split at depth edges) that dominates the box core."""
    import cv2

    if edges is None or mask.sum() < 30:
        return mask
    m = (mask & ~edges).astype(np.uint8)
    n, labels = cv2.connectedComponents(m, connectivity=4)
    if n <= 2:
        return mask
    h, w = mask.shape
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    core = _box_mask((h, w), [(x0 + bw * 0.2, y0 + bh * 0.3, x1 - bw * 0.2, y1 - bh * 0.05)])
    counts = np.bincount(labels[core & (m > 0)].ravel(), minlength=n)
    counts[0] = 0
    if counts.max() == 0:
        counts = np.bincount(labels[m > 0].ravel(), minlength=n)
        counts[0] = 0
    keep = labels == int(counts.argmax())
    keep = cv2.dilate(keep.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) & mask
    return keep if keep.sum() >= 20 else mask


def _place_by_center_depth(geom, box, prior) -> Optional[ObjectEstimate]:
    """Last resort: stand the object on the floor under its bbox center's depth."""
    x0, y0, x1, y1 = box
    pw, ph, pd = prior
    h, w = geom.valid.shape
    sub = _box_mask((h, w), [box]) & geom.valid
    if sub.sum() < 5:
        return None
    p = np.median(geom.points[sub], axis=0)
    b = geom.box
    if not (b.x_min < p[0] < b.x_max and b.z_min < p[2] < b.z_max):
        return None
    to_cam = geom.t - p
    return ObjectEstimate(
        center=(float(p[0]), 0.0, float(p[2])),
        dims=(round(pw, 3), round(ph, 3), round(pd, 3)),
        rot_y_deg=_snap_yaw(np.array([to_cam[0], 0.0, to_cam[2]])),
        confidence=0.25,
        method="center",
    )


def semantic_scale(cues: Sequence[Tuple[float, float, float]]) -> Optional[float]:
    """
    Metric-scale correction from objects of known size. Monocular metric depth
    is typically off by 10-30% per photo; standard furniture heights (tables
    0.75 m, counters 0.9 m, doors ~2.05 m) and the vision model's size
    estimates pin it down. cues: (expected, measured, weight) triples.
    Returns a multiplicative factor, or None when the evidence is too weak.
    """
    logs, weights = [], []
    for expected, measured, weight in cues:
        if expected and measured and expected > 0.05 and measured > 0.05 and weight > 0:
            r = expected / measured
            if 0.4 < r < 2.5:  # ignore wild outliers (wrong box, wrong object)
                logs.append(math.log(r))
                weights.append(weight)
    if sum(weights) < 1.5:
        return None
    order = np.argsort(logs)
    logs_s = np.array(logs)[order]
    w_s = np.array(weights)[order]
    cum = np.cumsum(w_s)
    median = float(logs_s[np.searchsorted(cum, cum[-1] / 2.0)])  # weighted median
    # Only act on consistent evidence: most of the weight must agree (+-10%)
    agree = w_s[np.abs(logs_s - median) < math.log(1.1)].sum()
    if agree < 0.6 * cum[-1] or agree < 1.5:
        return None
    return float(np.clip(math.exp(median), 0.7, 1.45))


def _place_flat(geom, box, prior, truncated_b) -> Optional[ObjectEstimate]:
    """
    Rugs: the rug lies on the floor plane. In perspective it is a trapezoid
    whose NEAR edge spans the bbox width, while the bbox's far corners
    overshoot it — so width comes from the near edge, depth from near to far.
    """
    x0, y0, x1, y1 = box
    pw, ph, pd = prior
    near_l, near_r = geom.floor_hit(x0, y1), geom.floor_hit(x1, y1)
    far = geom.floor_hit((x0 + x1) / 2.0, y0)
    if near_l is None or near_r is None or far is None:
        return None
    near = (near_l + near_r) / 2.0
    across = near_r - near_l
    along = far - near
    # Rugs follow the walls: snap to the room axis closest to the near edge
    along_x = abs(across[0]) >= abs(across[2])
    width = abs(across[0]) if along_x else abs(across[2])
    depth = abs(along[2]) if along_x else abs(along[0])
    center = (near + far) / 2.0
    if width < depth:
        width, depth = depth, width
        along_x = not along_x
    width = float(np.clip(width, 0.5, max(pw * 2.0, 1.0)))
    depth = float(np.clip(depth, 0.4, max(pd * 2.0, 1.0)))
    return ObjectEstimate(
        center=(float(center[0]), 0.0, float(center[2])),
        dims=(round(width, 3), 0.02, round(depth, 3)),
        rot_y_deg=0.0 if along_x else 90.0,
        confidence=0.5 if not truncated_b else 0.35,
        method="floor",
    )


# ---------------------------------------------------------------- wall features

def place_feature(geom: RoomGeometry, box: Sequence[float], ftype: str) -> Optional[FeatureEstimate]:
    """
    Put a window/door/art/mirror/curtain on the wall its rays actually hit.
    Rays are used instead of depth: glass and mirrors have meaningless depth.
    """
    x0, y0, x1, y1 = [float(v) for v in box]
    b = geom.box
    planes = geom.wall_planes()

    def hit(u: float, v: float, only: Optional[str] = None) -> Optional[Tuple[str, np.ndarray]]:
        d = geom.ray(u, v)
        best = None
        for name, (n, off) in planes.items():
            if only and name != only:
                continue
            denom = n @ d
            if abs(denom) < 1e-6:
                continue
            s = -(n @ geom.t + off) / denom
            if s <= 0:
                continue
            p = geom.t + s * d
            if name != only and not (
                b.x_min - 0.05 <= p[0] <= b.x_max + 0.05 and b.z_min - 0.05 <= p[2] <= b.z_max + 0.05
            ):
                continue
            if best is None or s < best[0]:
                best = (s, name, p)
        return (best[1], best[2]) if best else None

    if ftype == "pendant":
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        r = min(geom.points.shape[0] - 1, int(cy * geom.points.shape[0]))
        c = min(geom.points.shape[1] - 1, int(cx * geom.points.shape[1]))
        p = geom.points[r, c].copy()
        if not geom.valid[r, c]:
            return None
        # A small pendant's center pixel often hits the wall behind it: pull
        # it just inside the room
        p[0] = float(np.clip(p[0], b.x_min + 0.3, b.x_max - 0.3))
        p[2] = float(np.clip(p[2], b.z_min + 0.3, b.z_max - 0.3))
        bottom_ray = geom.ray(cx, y1)
        dist = np.linalg.norm((p - geom.t)[[0, 2]])
        horiz = np.linalg.norm(bottom_ray[[0, 2]]) + 1e-9
        y_bottom = float(geom.t[1] + bottom_ray[1] * dist / horiz)
        drop = float(np.clip(b.height - y_bottom, 0.3, b.height * 0.6))
        width = float(np.clip(np.linalg.norm(p - geom.t) * (x1 - x0) * geom.camera.width / geom.camera.fx, 0.15, 1.2))
        return FeatureEstimate(
            wall="ceiling", center_along=float(p[0]), width=width, bottom=0.0,
            height=drop, center_z=float(p[2]),
        )

    center = hit((x0 + x1) / 2.0, (y0 + y1) / 2.0)
    if center is None or center[0] == "front":
        return None
    wall = center[0]
    pts = [hit(u, v, only=wall) for u, v in (
        (x0, (y0 + y1) / 2), (x1, (y0 + y1) / 2), ((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1),
    )]
    if any(p is None for p in pts):
        return None
    (_, pl), (_, pr), (_, pt), (_, pb) = pts
    if wall == "back":
        a0, a1, wall_len, mid = pl[0], pr[0], b.width, (b.x_min + b.x_max) / 2.0
        along = lambda p: p[0] - mid  # noqa: E731
    elif wall == "left":
        # Scene JSON convention: position along side walls is measured on z
        a0, a1, wall_len, mid = pl[2], pr[2], b.depth, (b.z_min + b.z_max) / 2.0
        along = lambda p: p[2] - mid  # noqa: E731
    else:
        a0, a1, wall_len, mid = pl[2], pr[2], b.depth, (b.z_min + b.z_max) / 2.0
        along = lambda p: p[2] - mid  # noqa: E731
    width = float(np.clip(abs(a1 - a0), 0.2, wall_len - 0.05))
    c_along = float((along(pl) + along(pr)) / 2.0)
    c_along = float(np.clip(c_along, -wall_len / 2 + width / 2, wall_len / 2 - width / 2))
    top = float(np.clip(pt[1], 0.1, b.height))
    bottom = float(np.clip(pb[1], 0.0, top - 0.1))
    if y1 > 0.99:  # cut off at the bottom of the photo
        bottom = 0.0 if ftype in ("door", "curtain") else bottom
    if y0 < 0.01 and ftype in ("curtain", "window", "door"):
        top = min(b.height, max(top, b.height - 0.05))
    return FeatureEstimate(wall=wall, center_along=c_along, width=width, bottom=bottom, height=top - bottom)


# ---------------------------------------------------------------- materials

def rectified_floor_patch(
    image,
    geom: RoomGeometry,
    blocked: Optional[np.ndarray] = None,
    size_m: float = 1.2,
    out_px: int = 512,
):
    """
    Cut a top-down (perspective-corrected) square of real floor from the photo.
    Returns (PIL image, tile_size_m) or (None, None). The known metric size
    lets the editor tile it at the true scale (planks look like planks).
    blocked: (H, W) mask at analysis resolution of pixels to avoid (objects).
    """
    import cv2
    from PIL import Image

    h, w = geom.valid.shape
    floor = geom.structure == FLOOR
    if blocked is not None:
        floor &= ~blocked
    if floor.sum() < 200:
        return None, None
    fx = geom.points[..., 0][floor]
    fz = geom.points[..., 2][floor]
    best = None
    for s in (size_m, size_m * 0.75, size_m * 0.5):
        # Candidate square centers on a coarse grid over visible floor
        for cx in np.linspace(np.percentile(fx, 10), np.percentile(fx, 90), 7):
            for cz in np.linspace(np.percentile(fz, 10), np.percentile(fz, 90), 7):
                corners = np.array([
                    [cx - s / 2, 0.0, cz - s / 2], [cx + s / 2, 0.0, cz - s / 2],
                    [cx + s / 2, 0.0, cz + s / 2], [cx - s / 2, 0.0, cz + s / 2],
                ])
                uv, zc = geom.project(corners)
                if (zc <= 0.2).any() or (uv < 0.01).any() or (uv > 0.99).any():
                    continue
                # Coverage check on a grid inside the square
                g = np.linspace(-s / 2 * 0.9, s / 2 * 0.9, 6)
                gx, gz = np.meshgrid(cx + g, cz + g)
                samples = np.stack([gx.ravel(), np.zeros(gx.size), gz.ravel()], -1)
                suv, _ = geom.project(samples)
                cols = np.clip((suv[:, 0] * w).astype(int), 0, w - 1)
                rows = np.clip((suv[:, 1] * h).astype(int), 0, h - 1)
                cover = floor[rows, cols].mean()
                # Prefer big, fully clean, close-to-camera patches (more pixels)
                a, c = uv[1] - uv[0], uv[3] - uv[0]
                area_px = abs(a[0] * c[1] - a[1] * c[0])
                score = cover * 2.0 + area_px
                if cover >= 0.92 and (best is None or score > best[0]):
                    best = (score, uv, s)
        if best is not None:
            break
    if best is None:
        return None, None
    _, uv, s = best
    W, H = image.size
    src = (uv * np.array([W, H])).astype(np.float32)
    dst = np.array([[0, 0], [out_px, 0], [out_px, out_px], [0, out_px]], np.float32)
    # Row 0 of the texture = far edge (z - s/2): matches three.js plane UVs
    M = cv2.getPerspectiveTransform(src, dst)
    arr = np.asarray(image.convert("RGB"))
    warped = cv2.warpPerspective(arr, M, (out_px, out_px), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return Image.fromarray(warped), float(s)


def shell_visibility(geom: RoomGeometry, tol_m: float = 0.08, tol_rel: float = 0.02) -> np.ndarray:
    """
    Pixels where the photo shows the room shell itself — or something beyond
    it (a window view, a mirror's reflection) — rather than furniture in
    front of it: the measured depth reaches the box wall the ray exits
    through. Art, curtains, doors and TVs flat on a wall count as shell.
    """
    h, w = geom.valid.shape
    u, v = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    d = geom.camera.rays(u, v) @ geom.R.T  # camera rays (z=1) in room coords
    b, t = geom.box, geom.t
    exits = []
    for axis, lo, hi in ((0, b.x_min, b.x_max), (1, 0.0, b.height), (2, b.z_min, b.z_max)):
        da = d[..., axis]
        with np.errstate(divide="ignore", invalid="ignore"):
            s = np.where(da > 1e-9, (hi - t[axis]) / da, np.where(da < -1e-9, (lo - t[axis]) / da, np.inf))
        exits.append(s)
    # Rays have camera z = 1, so the exit parameter is the planar depth there
    exit_z = np.minimum.reduce(exits)
    measured_z = (geom.points - t) @ geom.R[:, 2]
    return ~geom.valid | (measured_z >= exit_z * (1.0 - tol_rel) - tol_m)


def structure_mask_image(geom: RoomGeometry, image_size: Tuple[int, int], dilate_px: int = 2):
    """
    Grayscale mask (photo resolution) of pixels that show the room shell:
    floor, walls, ceiling and what hangs flat on them. The editor projects
    the photo onto the shell only there, so furniture in the photo never
    leaves 'ghosts' on the walls.
    """
    import cv2
    from PIL import Image

    m = ((geom.structure > 0) | shell_visibility(geom)).astype(np.uint8) * 255
    k = np.ones((3, 3), np.uint8)
    m = cv2.erode(m, k, iterations=max(1, dilate_px // 2))
    m = cv2.resize(m, image_size, interpolation=cv2.INTER_LINEAR)
    m = cv2.GaussianBlur(m, (0, 0), sigmaX=max(1.0, image_size[0] / 400.0))
    return Image.fromarray(m, mode="L")
