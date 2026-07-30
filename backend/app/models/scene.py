"""
ReimagineAI - Structured 3D Scene models

A Scene is the source of truth for the editable 3D room:
a parametric room shell plus one SceneObject per furniture item.
The mobile editor renders it and edits it via SceneOp patches.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MaterialDef(BaseModel):
    """Simple PBR-ish material description the editor can apply."""
    color: str = "#CCCCCC"  # hex color
    texture: Optional[str] = None  # texture preset name (e.g. "oak_01"), optional
    texture_url: Optional[str] = None  # real texture sampled from the user's photo
    roughness: float = 0.9
    metalness: float = 0.0


class WallFeature(BaseModel):
    """
    Something on a wall or ceiling: window, door, curtain, art, pendant lamp.
    Rendered as part of the shell (recolorable, not movable like furniture).
    wall: back (the wall facing the camera in the photo) | left | right | front | ceiling.
    center_x_m: offset along the wall from its center, in meters.
    center_z_m: used only for ceiling features (pendants): z position in the room.
    """
    id: str
    type: str  # window | door | curtain | art | pendant | mirror
    style: Optional[str] = None  # window: standard|floor_to_ceiling|sliding_door; curtain: solid|sheer
    wall: str = "back"
    center_x_m: float = 0.0
    center_z_m: float = 0.0
    width_m: float = 1.2
    height_m: float = 1.4
    bottom_m: float = 0.8
    color: str = "#FFFFFF"


class RoomShell(BaseModel):
    """Parametric room box: floor + walls + ceiling with editable materials."""
    width_m: float = 4.0   # along X
    depth_m: float = 4.0   # along Z
    height_m: float = 2.6  # along Y
    wall_material: MaterialDef = Field(default_factory=lambda: MaterialDef(color="#F2EDE4"))
    floor_material: MaterialDef = Field(default_factory=lambda: MaterialDef(color="#A98B6D"))
    ceiling_material: MaterialDef = Field(default_factory=lambda: MaterialDef(color="#FFFFFF"))
    features: List[WallFeature] = Field(default_factory=list)


class Transform(BaseModel):
    pos: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])  # meters, y=0 is floor
    rot_y_deg: float = 0.0
    scale: List[float] = Field(default_factory=lambda: [1.0, 1.0, 1.0])


class AssetRef(BaseModel):
    """
    What 3D asset represents this object.
    - type "catalog": `ref` is a catalog entry id; the editor builds it procedurally
      (or loads its GLB when the catalog entry has one).
    - type "url": `ref` is a GLB URL (future: generated per-object meshes).
    """
    type: str = "catalog"
    ref: str


class SceneObject(BaseModel):
    id: str
    category: str                      # sofa, chair, table, bed, lamp_floor, ...
    label: str = ""                    # human-friendly name shown in the editor
    asset: AssetRef
    transform: Transform = Field(default_factory=Transform)
    dimensions_m: List[float] = Field(  # [width, height, depth] target size in meters
        default_factory=lambda: [1.0, 1.0, 1.0]
    )
    material_override: Optional[MaterialDef] = None
    source: Optional[Dict[str, Any]] = None  # detection provenance (bbox, confidence)


class SceneData(BaseModel):
    """The versioned JSON document stored in Postgres."""
    room_type: str = "living room"
    style: Optional[str] = None
    room: RoomShell = Field(default_factory=RoomShell)
    objects: List[SceneObject] = Field(default_factory=list)


class SceneOp(BaseModel):
    """
    One edit operation, applied server-side and mirrored in the editor.

    op: move | rotate | scale | recolor | material | swap | remove | add | set_room
    target: object id, or "wall" / "floor" / "ceiling" for shell edits (unused for add/set_room)
    value: op-specific payload, e.g. {"pos": [x,y,z]}, {"color": "#334455"},
           {"ref": "sofa_l_shape"}, {"object": {...SceneObject...}},
           {"width_m": 4.5, "wall_color": "#DDD8CC"}
    """
    op: str
    target: Optional[str] = None
    value: Dict[str, Any] = Field(default_factory=dict)


# ============ API request/response models ============

class SceneGenerationRequest(BaseModel):
    image_base64: str
    conversation_id: Optional[str] = None
    title: Optional[str] = None


class SceneResponse(BaseModel):
    scene_id: str
    title: str
    version: int
    data: SceneData
    conversation_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SceneSummary(BaseModel):
    scene_id: str
    title: str
    version: int
    room_type: str
    object_count: int
    updated_at: Optional[datetime] = None


class SceneOpsRequest(BaseModel):
    ops: List[SceneOp]
    base_version: Optional[int] = None  # optimistic concurrency (warn-only)


class SceneNLEditRequest(BaseModel):
    instruction: str


class SceneNLEditResponse(BaseModel):
    scene_id: str
    version: int
    data: SceneData
    applied_ops: List[SceneOp]
    message: str
