"""
ReimagineAI - Scene semantics tests

TypeSafe judgments are policy-tested with a fake client (thresholds,
no-match handling, fallbacks); plus catalog matching, box-format handling,
the NL-edit fast path, mesh flip detection and the chat keyword fallback.
No network, database or models.
"""
import asyncio
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import semantic_service as sem_mod  # noqa: E402
from app.services.catalog_service import catalog_service  # noqa: E402
from app.services.scene_service import COLOR_MAP, scene_service  # noqa: E402
from app.models.scene import SceneOp  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def choice(value, confidence):
    return SimpleNamespace(choice=value, confidence=confidence, probabilities={value: confidence})


def noul(p):
    return SimpleNamespace(noul=p)


@pytest.fixture
def typesafe(monkeypatch):
    """Enable the service with a scripted fake response."""
    monkeypatch.setattr(sem_mod.settings, "typesafe_api_key", "test-key")
    state = {}

    async def fake_ask(state_, questions):
        state["questions"] = questions
        state["state"] = state_
        return state.get("response")

    monkeypatch.setattr(sem_mod.semantic_service, "_ask", fake_ask)
    return state


# ---------------- catalog ----------------

def test_aliases_no_longer_hide_real_categories():
    assert catalog_service.normalize_category("stool") == "stool"
    assert catalog_service.normalize_category("bench") == "bench"
    assert catalog_service.normalize_category("console") == "console"
    assert catalog_service.normalize_category("grey table lamp") == "lamp_table"
    assert catalog_service.normalize_category("bedside table") == "nightstand"
    assert catalog_service.normalize_category("round side table") == "side_table"


def test_match_label_picks_the_shape():
    assert catalog_service.match_label("round jute rug", "rug", 1.5)["id"] == "rug_round"
    assert catalog_service.match_label("grey L-shaped sectional", "sofa", 2.6)["id"] == "sofa_l_shape"
    assert catalog_service.match_label("office chair", "chair")["id"] == "chair_office"
    assert catalog_service.match_label("king size bed", "bed")["id"] == "bed_king"
    assert catalog_service.match_label("velvet sofa", "sofa", 1.6)["id"] == "sofa_loveseat"
    # A lamp standing on furniture is a table lamp whatever the category says
    assert catalog_service.match_label("ceramic lamp", "lamp", 0.4, on_furniture=True)["category"] == "lamp_table"
    assert catalog_service.match_label("curtain", "curtain") is None


# ---------------- TypeSafe policy ----------------

def test_disabled_service_defers_to_rules(monkeypatch):
    monkeypatch.setattr(sem_mod.settings, "typesafe_api_key", "")
    objs = [{"label": "sofa", "category": "sofa"}]
    assert run(sem_mod.semantic_service.match_catalog(objs, "living room")) == [None]
    assert run(sem_mod.semantic_service.route_chat("make it blue", None, True, True)) is None
    assert run(sem_mod.semantic_service.parse_scene_edit("make the sofa blue", [], ["blue"])) is None


def test_catalog_choices_are_confidence_gated(typesafe):
    objs = [
        {"label": "grey L-shaped sectional", "category": "sofa", "width_m": 2.7},
        {"label": "sheer curtain", "category": "curtain"},
        {"label": "chair", "category": "chair"},
    ]
    typesafe["response"] = SimpleNamespace(choices={
        "item_0": choice("sofa_l_shape", 0.93),
        "item_1": choice("none", 0.9),
        "item_2": choice("chair_office", 0.41),  # too unsure: rules decide
    }, nouls={})
    assert run(sem_mod.semantic_service.match_catalog(objs, "living room")) == ["sofa_l_shape", "none", None]
    # Options stay within related categories, plus the no-match option
    options = set(typesafe["questions"]["item_0"].criteria)
    assert "sofa_l_shape" in options and "none" in options and "bed_double" not in options
    # Sizes are words, not numbers (Jev is weak with numeric values)
    assert "wide" in typesafe["state"]["items"][0]["size"]


def test_chat_route(typesafe):
    typesafe["response"] = SimpleNamespace(
        choices={"intent": choice("change_room", 0.88)}, nouls={"scene_edit": noul(0.91)})
    route = run(sem_mod.semantic_service.route_chat("paint the walls sage", "Hi!", True, True))
    assert route.intent == "change_room" and route.scene_edit > 0.9


def test_scene_edit_fast_path_rules(typesafe):
    objs = [{"id": "sofa_ab12cd", "category": "sofa", "label": "grey sofa"}]
    names = list(COLOR_MAP)

    def respond(action, target=("sofa_ab12cd", 0.95), color=("navy", 0.9), multiple=0.05):
        typesafe["response"] = SimpleNamespace(choices={
            "action": choice(*action), "target": choice(*target), "color": choice(*color),
            "rotation": choice("unspecified", 0.9),
        }, nouls={"multiple": noul(multiple)})

    respond(("recolor_object", 0.95))
    assert run(sem_mod.semantic_service.parse_scene_edit("make the sofa navy", objs, names)) == {
        "action": "recolor_object", "target": "sofa_ab12cd", "color": "navy"}
    respond(("recolor_object", 0.95), multiple=0.8)          # several changes -> GPT
    assert run(sem_mod.semantic_service.parse_scene_edit("x", objs, names)) is None
    respond(("other", 0.99))                                   # move/add/swap -> GPT
    assert run(sem_mod.semantic_service.parse_scene_edit("x", objs, names)) is None
    respond(("remove_object", 0.9), target=("sofa_ab12cd", 0.5))  # unsure target -> GPT
    assert run(sem_mod.semantic_service.parse_scene_edit("x", objs, names)) is None
    respond(("recolor_walls", 0.92), color=("other", 0.8))     # color not in the list -> GPT
    assert run(sem_mod.semantic_service.parse_scene_edit("x", objs, names)) is None


def test_nl_edit_uses_fast_path_without_gpt(monkeypatch):
    data = {
        "room": {"width_m": 4, "depth_m": 4},
        "objects": [{
            "id": "bed_111111", "category": "bed", "label": "bed",
            "transform": {"pos": [0, 0, -1], "rot_y_deg": 90.0, "scale": [1, 1, 1]},
            "material_override": {"color": "#8A8A8A"},
        }],
    }

    async def fake_parse(instruction, objects, color_names):
        assert objects[0]["color_name"] in ("grey", "gray")
        assert "back wall" in objects[0]["where"]
        return {"action": "rotate_object", "target": "bed_111111", "rotate_deg": 180.0}

    def no_gpt(*a, **k):
        raise AssertionError("GPT must not be called for simple edits")

    monkeypatch.setattr(sem_mod.semantic_service, "parse_scene_edit", fake_parse)
    monkeypatch.setattr("app.services.scene_service.openai_service.client",
                        SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=no_gpt))))
    ops = run(scene_service.parse_nl_edit(data, "turn the bed around"))
    assert ops == [SceneOp(op="rotate", target="bed_111111", value={"rot_y_deg": 270.0})]


def test_shell_recolor_turns_off_photo_projection():
    data = {"room": {"wall_material": {"color": "#FFFFFF", "texture_url": "/x.jpg", "photo_projection": True}},
            "objects": []}
    scene_service._apply_op(data, SceneOp(op="recolor", target="wall", value={"color": "#1A1A1C"}))
    wm = data["room"]["wall_material"]
    assert wm["color"] == "#1A1A1C" and wm["texture_url"] is None and wm["photo_projection"] is False


# ---------------- vision box formats ----------------

def test_box_formats_are_canonicalized():
    from app.services.scene_builder import scene_builder

    size = (1000, 500)
    det = {
        "objects": [
            {"label": "bed", "box_2d": [500, 100, 1000, 600]},   # Gemini [ymin, xmin, ymax, xmax] / 1000
            {"label": "lamp", "bbox": [700, 100, 800, 300]},     # OpenAI pixels [x0, y0, x1, y1]
            {"label": "ghost"},                                   # no box -> dropped
        ],
        "features": [],
        "floor_sample_box_2d": [900, 0, 1000, 200],
    }
    out = scene_builder._canonicalize(det, size)
    # Boxless objects stay (relations index into this list) but are skipped
    assert [o["label"] for o in out["objects"]] == ["bed", "lamp", "ghost"]
    assert out["objects"][2]["_skip"] is True
    assert out["objects"][0]["bbox"] == [100, 250, 600, 500]
    assert out["objects"][0]["box"] == pytest.approx([0.1, 0.5, 0.6, 1.0])
    assert out["objects"][1]["box"] == pytest.approx([0.7, 0.2, 0.8, 0.6])
    assert out["floor_sample_bbox"] == [0, 450, 200, 500]
    # Round trip into Gemini's native format for the review pass
    rendered = scene_builder._render_boxes(out, "gemini", size)
    assert rendered["objects"][0]["box_2d"] == [500, 100, 1000, 600] and "bbox" not in rendered["objects"][0]


# ---------------- generated mesh alignment ----------------

def test_fit_scale_follows_visible_dims():
    from app.services.mesh_alignment import fit_scale

    # A bed mesh: width and height follow the photo's measurement
    sx, sy, sz = fit_scale([0.68, 0.2, 1.0], [1.6, 0.6, 2.05])
    assert sx == pytest.approx(1.6 / 0.68) and sy == pytest.approx(0.6 / 0.2)
    assert sz == pytest.approx(2.05)                  # depth within +-25% of the mean scale
    # A generator that made a nightstand 2.3x too flat is stretched at most 2x
    sx, sy, sz = fit_scale([1.0, 0.24, 1.0], [0.693, 0.389, 0.576])
    assert sy == pytest.approx(2.0 * sx)
    assert sz == pytest.approx(0.75 * math.sqrt(sx * sy))


def test_flip_detection_finds_a_sideways_mesh(tmp_path):
    trimesh = pytest.importorskip("trimesh")
    from app.services import mesh_alignment as ma

    # An L-shaped "chaise sofa" mesh, front on +Z, but generated turned 90 degrees
    base = trimesh.creation.box(extents=[2.0, 0.5, 0.9], transform=trimesh.transformations.translation_matrix([0, 0.25, 0]))
    chaise = trimesh.creation.box(extents=[0.8, 0.5, 0.9], transform=trimesh.transformations.translation_matrix([-0.6, 0.25, 0.9]))
    mesh = trimesh.util.concatenate([base, chaise])
    true_obj = {"dimensions_m": [2.0, 0.5, 1.8], "transform": {"pos": [0.0, 0.0, -1.0], "rot_y_deg": 0.0}}
    camera = {"position": [1.5, 1.4, 2.5], "fov_deg": 45.0, "aspect": 1.5}
    # Look at the object: build the camera quaternion from a lookAt basis
    fwd = np.array([0.0, 0.3, -1.0]) - np.array(camera["position"])
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, [0, 1, 0]); right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    rot = np.stack([right, up, -fwd], axis=1)
    from app.services.room_geometry import _quat_from_matrix
    camera["quaternion"] = list(_quat_from_matrix(rot))

    size = (600, 400)
    # The photo shows the sofa as it really stands; the GLB was built turned by -90
    pts_true = ma.place_points(np.asarray(mesh.sample(4000, seed=1) if hasattr(mesh, "sample") else mesh.vertices), true_obj, 0.0)
    uv, ok = ma.project(camera, pts_true, size)
    alpha_full = ma._silhouette(uv[ok], (size[1], size[0]))
    turned = mesh.copy()
    turned.apply_transform(trimesh.transformations.rotation_matrix(-math.pi / 2, [0, 1, 0]))
    path = tmp_path / "gen.glb"
    turned.export(path)
    offset, scores = ma.choose_yaw_offset(str(path), true_obj, camera, size, (0, 0, size[0], size[1]), alpha_full)
    assert offset == 90.0, scores
    # A mesh already facing the right way keeps offset 0
    mesh.export(tmp_path / "ok.glb")
    offset, _ = ma.choose_yaw_offset(str(tmp_path / "ok.glb"), true_obj, camera, size, (0, 0, size[0], size[1]), alpha_full)
    assert offset == 0.0


# ---------------- chat keyword fallback ----------------

def test_edit_keywords_match_whole_words_only():
    from app.routers.chat import _is_edit_request

    assert _is_edit_request("make the walls sage green")
    assert _is_edit_request("Could you remove the rug?")
    assert not _is_edit_request("what a lovely bedroom")    # not "bed"
    assert not _is_edit_request("what's your address?")     # not "add"
    assert not _is_edit_request("I'll return tomorrow")     # not "turn"


# ---------------- regressions from review ----------------

def test_boxless_objects_keep_relation_indices():
    from app.services.scene_builder import scene_builder

    det = {"objects": [
        {"label": "nightstand", "category": "nightstand", "bbox": [10, 10, 50, 60]},
        {"label": "ghost"},                                                          # no box
        {"label": "lamp", "category": "lamp", "bbox": [20, 0, 30, 10],
         "relations": [{"type": "on", "target": 0}]},
    ], "features": []}
    out = scene_builder._canonicalize(det, (100, 100))
    assert [o["label"] for o in out["objects"]] == ["nightstand", "ghost", "lamp"]
    assert out["objects"][1]["_skip"] is True and "box" not in out["objects"][1]
    assert out["objects"][2]["relations"][0]["target"] == 0  # still the nightstand
    # Internal flags never reach the model in the review prompt
    assert "_skip" not in scene_builder._render_boxes(out, "openai", (100, 100))["objects"][1]


def test_malformed_model_output_is_coerced():
    from app.services.scene_builder import scene_builder

    det = {
        "room_type": 7, "style": {"x": 1}, "wall_color": "greyish", "floor_color": "#a98b6d",
        "objects": [{"label": 12, "category": ["sofa"], "facing": 90, "color": "red",
                     "bbox": [0, 0, 50, 50], "relations": "against"}],
        "features": [{"type": {"t": 1}, "style": 3, "bbox": [0, 0, 10, 10]}],
    }
    out = scene_builder._canonicalize(det, (100, 100))
    o = out["objects"][0]
    assert o["label"] == "12" and o["category"] is None and o["facing"] == "90"
    assert o["color"] is None and o["relations"] == []
    assert out["room_type"] == "7" and out["style"] is None
    assert out["wall_color"] is None and out["floor_color"] == "#A98B6D"
    assert out["features"][0]["type"] is None and out["features"][0]["style"] == "3"


def test_recolors_turn_off_photo_projection():
    data = {"room": {
        "wall_material": {"color": "#FFFFFF", "texture_url": "/w.jpg", "photo_projection": True},
        "floor_material": {"color": "#FFFFFF", "texture_url": "/f.jpg", "photo_projection": True},
        "features": [{"id": "window_1", "color": "#EEEEEE", "photo_projection": True}],
    }, "objects": []}
    scene_service._apply_op(data, SceneOp(op="recolor", target="window_1", value={"color": "#223344"}))
    assert data["room"]["features"][0]["photo_projection"] is False
    scene_service._apply_op(data, SceneOp(op="set_room", value={"floor_color": "#554433"}))
    fm = data["room"]["floor_material"]
    assert fm["color"] == "#554433" and fm["texture_url"] is None and fm["photo_projection"] is False


def test_proposals_skip_the_keyword_fast_path(monkeypatch):
    """'Your light grey walls could be navy' must not paint the walls light grey."""
    calls = {}

    async def fake_create(**kwargs):
        calls["prompt"] = kwargs["messages"][1]["content"]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content='{"ops": [{"op": "recolor", "target": "wall", "value": {"color": "#1F3A5F"}}]}'))])

    async def no_fast(*a, **k):
        raise AssertionError("fast paths must be skipped for proposals")

    monkeypatch.setattr(sem_mod.semantic_service, "parse_scene_edit", no_fast)
    monkeypatch.setattr("app.services.scene_service.openai_service.client",
                        SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create))))
    text = "Apply the change proposed here: Your walls are currently light grey; I suggest navy."
    assert scene_service._rule_based_shell_ops(text)[0].value["color"] == COLOR_MAP["light grey"]  # the trap
    ops = run(scene_service.parse_nl_edit({"room": {}, "objects": []}, text, fast_paths=False))
    assert ops[0].value["color"] == "#1F3A5F" and "navy" in calls["prompt"]


def test_typesafe_failures_never_escape(monkeypatch):
    monkeypatch.setattr(sem_mod.settings, "typesafe_api_key", "test-key")

    def boom(*a, **k):
        raise RuntimeError("broken SDK")

    monkeypatch.setattr(sem_mod.catalog_service, "normalize_category", boom)
    assert run(sem_mod.semantic_service.match_catalog([{"label": "sofa"}, {"label": "bed"}], "room")) == [None, None]
    monkeypatch.setattr(sem_mod.semantic_service, "_route_chat", boom)
    assert run(sem_mod.semantic_service.route_chat("hi", None, False, False)) is None
    monkeypatch.setattr(sem_mod.semantic_service, "_parse_scene_edit", boom)
    assert run(sem_mod.semantic_service.parse_scene_edit("make it blue", [], ["blue"])) is None
