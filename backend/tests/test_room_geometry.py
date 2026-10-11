"""
ReimagineAI - Room geometry tests on synthetic rooms

A box room with furniture is ray-cast from a known camera into an exact depth
map; the measured reconstruction must recover the camera, the walls, the
furniture and the wall features, and the exported editor camera must
reproject points onto the pixels they came from. No models or network.
"""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import mesh_alignment, room_geometry as rg  # noqa: E402

W, H = 320, 240


def _camera_axes(yaw_deg, pitch_deg):
    """Columns right/down/forward in room coords; yaw 0 looks at -Z."""
    p = math.radians(pitch_deg)
    right = np.array([1.0, 0.0, 0.0])
    down = np.array([0.0, -math.cos(p), math.sin(p)])
    fwd = np.array([0.0, -math.sin(p), -math.cos(p)])
    y = math.radians(yaw_deg)
    Ry = np.array([[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]])
    return np.stack([Ry @ right, Ry @ down, Ry @ fwd], axis=1)


class SyntheticRoom:
    """Room [-w/2, w/2] x [0, h] x [-d/2, d/2] with axis-aligned boxes inside."""

    def __init__(self, w=4.0, d=5.0, h=2.6, cam=(0.6, 1.4, 1.8), yaw=20.0, pitch=6.0, hfov=65.0):
        self.w, self.d, self.h = w, d, h
        self.cam = np.array(cam, dtype=float)
        self.R = _camera_axes(yaw, pitch)
        self.f = (W / 2) / math.tan(math.radians(hfov) / 2)
        self.hfov = hfov
        self.boxes = []  # (lo, hi)

    def add_box(self, lo, hi):
        self.boxes.append((np.array(lo, float), np.array(hi, float)))

    def rays(self):
        u, v = np.meshgrid(np.arange(W) + 0.5, np.arange(H) + 0.5)
        rc = np.stack([(u - W / 2) / self.f, (v - H / 2) / self.f, np.ones_like(u)], -1)
        return rc @ self.R.T  # z_cam = 1, so the ray parameter is planar depth

    def depth(self):
        d = self.rays()
        o = self.cam
        lo = np.array([-self.w / 2, 0.0, -self.d / 2])
        hi = np.array([self.w / 2, self.h, self.d / 2])
        with np.errstate(divide="ignore", invalid="ignore"):
            t_room = np.min(np.stack([
                np.where(d[..., a] > 0, (hi[a] - o[a]) / d[..., a],
                         np.where(d[..., a] < 0, (lo[a] - o[a]) / d[..., a], np.inf))
                for a in range(3)
            ]), axis=0)
            depth = t_room
            for blo, bhi in self.boxes:
                t1 = (blo - o) / d
                t2 = (bhi - o) / d
                tn = np.max(np.minimum(t1, t2), axis=-1)
                tf = np.min(np.maximum(t1, t2), axis=-1)
                hit = (tf >= tn) & (tn > 0)
                depth = np.where(hit & (tn < depth), tn, depth)
        return depth.astype(np.float32)

    def project(self, p):
        pc = (np.asarray(p, float) - self.cam) @ self.R
        return np.stack([(pc[:, 0] / pc[:, 2] * self.f + W / 2) / W,
                         (pc[:, 1] / pc[:, 2] * self.f + H / 2) / H], -1)

    def bbox(self, lo, hi):
        corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        uv = self.project(corners)
        return [float(uv[:, 0].min()), float(uv[:, 1].min()), float(uv[:, 0].max()), float(uv[:, 1].max())]


@pytest.fixture(scope="module")
def room():
    r = SyntheticRoom()
    r.bed = ([-0.8, 0.0, -2.5], [0.8, 0.55, -0.45])      # against the back wall
    r.table = ([-1.7, 0.0, -1.0], [-1.1, 0.75, -0.4])    # free-standing, left of the bed
    for lo, hi in (r.bed, r.table):
        r.add_box(lo, hi)
    r.geom = rg.analyze_room(r.depth(), (W, H), fov_hint=r.hfov, fov_source="exif",
                             estimate={"width_m": 4.0, "depth_m": 5.0, "height_m": 2.6})
    assert r.geom is not None
    return r


def test_camera_and_room_are_recovered(room):
    g, q = room.geom, room.geom.quality
    assert q["camera_height_m"] == pytest.approx(1.4, abs=0.03)
    assert q["pitch_deg"] == pytest.approx(6.0, abs=1.0)
    assert abs(q["roll_deg"]) < 1.0
    # Wall directions are found modulo 90 degrees
    assert abs(((abs(q["wall_yaw_deg"]) + 45) % 90) - 45 - 20.0) < 2.0 or abs(abs(q["wall_yaw_deg"]) - 20.0) < 2.0
    assert g.box.height == pytest.approx(2.6, abs=0.06)
    assert g.box.observed["back"] and g.box.observed["ceiling"]
    # Back wall distance from the camera along the room axis
    assert g.t[2] - g.box.z_min == pytest.approx(1.8 + 2.5, abs=0.1)
    # The camera stands inside the reconstructed room
    assert g.box.x_min < g.t[0] < g.box.x_max and g.box.z_min < g.t[2] < g.box.z_max


def test_editor_camera_reprojects_points_onto_their_pixels(room):
    g = room.geom
    cam = g.editor_camera()
    h, w = g.valid.shape
    rows, cols = np.nonzero(g.valid)
    pick = np.linspace(0, len(rows) - 1, 200).astype(int)
    pts = g.points[rows[pick], cols[pick]]
    uv, ok = mesh_alignment.project(cam, pts, (w, h))
    assert ok.all()
    err = np.hypot(uv[:, 0] - (cols[pick] + 0.5), uv[:, 1] - (rows[pick] + 0.5))
    assert np.median(err) < 0.5 and err.max() < 1.5  # sub-pixel round trip


def test_furniture_is_measured(room):
    g = room.geom
    bed = rg.place_object(g, room.bbox(*room.bed), [1.6, 0.9, 2.05], facing="camera",
                          wall_hugger=True, stackable=False)
    assert bed is not None and bed.method == "depth"
    assert bed.against_wall == "back" and bed.rot_y_deg == 0.0
    assert bed.dims[0] == pytest.approx(1.6, rel=0.12)
    assert bed.dims[1] == pytest.approx(0.55, abs=0.08)
    assert bed.center[1] == 0.0
    # Flush with the back wall, as in the room
    assert bed.center[2] - bed.dims[2] / 2 == pytest.approx(g.box.z_min, abs=0.08)

    table = rg.place_object(g, room.bbox(*room.table), [0.6, 0.75, 0.6], facing="camera", stackable=False)
    assert table is not None
    assert table.dims[1] == pytest.approx(0.75, abs=0.08)
    # Same spot relative to the back wall and the bed
    assert (table.center[2] - g.box.z_min) == pytest.approx(-0.7 + 2.5, abs=0.2)
    assert (table.center[0] - bed.center[0]) == pytest.approx(-1.4, abs=0.2)


def test_window_lands_on_its_wall(room):
    # A window drawn on the back wall: 1.2 m wide, 1.0 m tall, sill at 0.9 m
    lo, hi = [-0.9, 0.9, -2.5], [0.3, 1.9, -2.5]
    est = rg.place_feature(room.geom, room.bbox(lo, hi), "window")
    assert est is not None and est.wall == "back"
    assert est.width == pytest.approx(1.2, abs=0.1)
    assert est.bottom == pytest.approx(0.9, abs=0.08)
    assert est.height == pytest.approx(1.0, abs=0.1)


def test_shell_mask_excludes_furniture(room):
    g = room.geom
    vis = rg.shell_visibility(g)
    h, w = vis.shape
    x0, y0, x1, y1 = room.bbox(*room.table)
    inside = vis[int((y0 + 0.25 * (y1 - y0)) * h):int((y1 - 0.1 * (y1 - y0)) * h),
                 int((x0 + 0.25 * (x1 - x0)) * w):int((x1 - 0.25 * (x1 - x0)) * w)]
    assert inside.mean() < 0.1           # the table is not shell
    assert vis[2:10, 2:10].mean() > 0.9  # ceiling/wall corner is


def test_rescale_keeps_reprojection(room):
    import copy

    g = copy.deepcopy(room.geom)
    before = g.editor_camera()
    rg.rescale(g, 1.1)
    after = g.editor_camera()
    assert after["position"][1] == pytest.approx(before["position"][1] * 1.1, rel=1e-3)
    assert after["quaternion"] == before["quaternion"] and after["fov_deg"] == before["fov_deg"]


def test_manhattan_self_calibration_finds_the_lens():
    r = SyntheticRoom(yaw=35.0, pitch=8.0, hfov=70.0, cam=(0.8, 1.3, 1.6))
    g = rg.analyze_room(r.depth(), (W, H))  # no EXIF, no model FOV
    assert g is not None
    assert g.camera.source == "manhattan"
    assert g.quality["hfov_deg"] == pytest.approx(70.0, abs=5.0)


def test_semantic_scale_needs_agreeing_evidence():
    assert rg.semantic_scale([(0.75, 0.68, 1.0), (0.9, 0.82, 1.0)]) == pytest.approx(1.1, abs=0.02)
    # Conflicting cues: no correction
    assert rg.semantic_scale([(0.75, 0.5, 1.0), (0.9, 1.2, 1.0)]) is None
    assert rg.semantic_scale([(0.75, 0.7, 0.3)]) is None  # too weak


def test_no_floor_means_no_geometry():
    depth = np.full((H, W), 3.0, np.float32)  # a flat wall filling the frame
    assert rg.analyze_room(depth, (W, H), fov_hint=60, fov_source="exif") is None


@pytest.mark.parametrize("true_hfov,hint,pitch", [(25.0, 24.0, 22.0), (118.0, 120.5, 6.0)])
def test_telephoto_and_ultrawide_photos_reconstruct(true_hfov, hint, pitch):
    # Model FOV estimates outside the usual lens range used to crash the
    # refinement search (empty window -> ValueError -> layout-only fallback)
    r = SyntheticRoom(yaw=25.0, pitch=pitch, hfov=true_hfov)
    g = rg.analyze_room(r.depth(), (W, H), fov_hint=hint, fov_source="moge-2")
    assert g is not None
    assert g.quality["camera_height_m"] == pytest.approx(1.4, abs=0.1)


def test_badly_wrong_fov_hint_degrades_without_crashing():
    r = SyntheticRoom(yaw=25.0, pitch=6.0, hfov=65.0)
    rg.analyze_room(r.depth(), (W, H), fov_hint=24.0, fov_source="moge-2")  # may be None; must not raise


def test_non_string_facing_is_ignored(room):
    est = rg.place_object(room.geom, room.bbox(*room.table), [0.6, 0.75, 0.6], facing=90, stackable=False)
    assert est is not None
