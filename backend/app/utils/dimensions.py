from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class ParsedDimensions:
    values: List[float]
    unit: str  # one of: "mm", "cm", "m", "in", "ft", "unknown"


_NUM_RE = re.compile(r"(?<!\w)(\d+(?:\.\d+)?)(?!\w)")


def _detect_unit(text: str) -> str:
    s = (text or "").lower()
    # Order matters: match longer tokens first
    if "millimeter" in s or "millimetre" in s or re.search(r"\bmm\b", s):
        return "mm"
    if "centimeter" in s or "centimetre" in s or re.search(r"\bcm\b", s):
        return "cm"
    # Avoid treating "mi" or other tokens as meters; require clear m markers
    if re.search(r"\bmeters?\b", s) or re.search(r"\bmetres?\b", s) or re.search(r"(?<!c)\bm\b", s):
        return "m"
    if "inch" in s or re.search(r"\bin\b", s) or '"' in s:
        return "in"
    if "feet" in s or re.search(r"\bft\b", s) or "'" in s:
        return "ft"
    return "unknown"


def parse_dimensions(text: Optional[str]) -> Optional[ParsedDimensions]:
    """
    Best-effort parser for product dimension strings.

    Examples it can handle:
    - '160 x 80 x 60 cm'
    - '63\" x 31.5\" x 23.6\"'
    - '5x7 ft'
    - '40 inch'
    """
    if not text:
        return None

    s = str(text).strip()
    if not s:
        return None

    unit = _detect_unit(s)
    nums = [float(m.group(1)) for m in _NUM_RE.finditer(s)]
    if not nums:
        return None

    # Heuristic: dimensions are usually 1–3 numbers; keep the first 3.
    values = nums[:3]
    return ParsedDimensions(values=values, unit=unit)


def _convert_value(value: float, src_unit: str, dst_unit: str) -> float:
    if src_unit == dst_unit:
        return value

    # Convert to centimeters first (as a hub), then to destination.
    if src_unit == "mm":
        cm = value / 10.0
    elif src_unit == "cm":
        cm = value
    elif src_unit == "m":
        cm = value * 100.0
    elif src_unit == "in":
        cm = value * 2.54
    elif src_unit == "ft":
        cm = value * 30.48
    else:
        raise ValueError(f"Unsupported source unit: {src_unit}")

    if dst_unit == "cm":
        return cm
    if dst_unit == "in":
        return cm / 2.54
    raise ValueError(f"Unsupported destination unit: {dst_unit}")


def _format_number(value: float, *, max_decimals: int) -> str:
    if max_decimals <= 0:
        return str(int(round(value)))
    s = f"{value:.{max_decimals}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def normalize_dimensions_string(
    raw: Optional[str],
    *,
    unit_system: Optional[str],
    kind: str = "product",
) -> Optional[str]:
    """
    Normalize a raw dimension string into a consistent unit based on unit_system.

    - Metric: products -> cm
    - Imperial: products -> in

    Returns a cleaned string like '160 × 80 × 60 cm' or '63 × 31.5 × 23.6 in'.
    If parsing fails, returns the original string.
    """
    if not raw:
        return None

    parsed = parse_dimensions(raw)
    if not parsed or parsed.unit == "unknown":
        return str(raw).strip() or None

    sys = (unit_system or "metric").strip().lower()
    if kind == "product":
        target_unit = "cm" if sys != "imperial" else "in"
    else:
        target_unit = "cm" if sys != "imperial" else "in"

    try:
        converted = [
            _convert_value(v, parsed.unit, target_unit) for v in parsed.values
        ]
    except Exception:
        return str(raw).strip() or None

    # Formatting: keep products readable (cm tends to be integer-ish; inches may need 1 decimal)
    max_decimals = 0 if target_unit == "cm" else 1
    formatted = " × ".join(_format_number(v, max_decimals=max_decimals) for v in converted)
    return f"{formatted} {target_unit}"


def compute_area_sqm(
    *,
    yard_length: Optional[float],
    yard_width: Optional[float],
    unit_system: Optional[str],
) -> Optional[float]:
    if yard_length is None or yard_width is None:
        return None
    if yard_length <= 0 or yard_width <= 0:
        return None

    sys = (unit_system or "metric").strip().lower()
    if sys == "imperial":
        length_m = float(yard_length) * 0.3048
        width_m = float(yard_width) * 0.3048
    else:
        length_m = float(yard_length)
        width_m = float(yard_width)
    return max(0.0, length_m * width_m)


def format_yard_dimensions(
    *,
    yard_length: Optional[float],
    yard_width: Optional[float],
    unit_system: Optional[str],
) -> Optional[str]:
    if yard_length is None or yard_width is None or yard_length <= 0 or yard_width <= 0:
        return None

    sys = (unit_system or "metric").strip().lower()
    unit = "m" if sys != "imperial" else "ft"
    # Yard dims: allow one decimal (meters/feet)
    l = _format_number(float(yard_length), max_decimals=1)
    w = _format_number(float(yard_width), max_decimals=1)
    return f"{l} {unit} × {w} {unit}"


def format_area(
    *,
    area_sqm: Optional[float],
    unit_system: Optional[str],
) -> Optional[str]:
    if area_sqm is None or area_sqm <= 0:
        return None

    sys = (unit_system or "metric").strip().lower()
    if sys == "imperial":
        area_ft2 = float(area_sqm) * 10.763910416709722
        return f"{_format_number(area_ft2, max_decimals=0)} ft²"
    return f"{_format_number(float(area_sqm), max_decimals=1)} m²"

