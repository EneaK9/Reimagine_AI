"""
Run the room upgrade pipeline from a local image file.

Example:
    python scripts/test_room_upgrade_pipeline.py \
        --image ~/Desktop/yard.jpg \
        --prompt "How can this look better with just $100?" \
        --budget 100
"""
import argparse
import asyncio
import base64
import json
import mimetypes
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test the room upgrade pipeline with a local image file."
    )
    parser.add_argument("--image", required=True, help="Path to a room/yard image.")
    parser.add_argument(
        "--prompt",
        required=True,
        help='User request, e.g. "How can this look better with just $100?"',
    )
    parser.add_argument("--budget", type=float, required=True, help="Budget amount.")
    parser.add_argument("--currency", default="USD", help="Currency code.")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000/api/v1",
        help="Backend API base URL when --use-http is set.",
    )
    parser.add_argument(
        "--use-http",
        action="store_true",
        help="Call a running backend server instead of running the pipeline in-process.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/room_upgrade_tests",
        help="Directory for JSON and generated image outputs.",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Optional output filename prefix, e.g. lawn1.",
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Stop after product search and budget optimization.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    image_path = Path(args.image).expanduser().resolve()
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")

    print("[1/3] Analyzing scene and finding products...")
    if args.use_http:
        analyze_result = analyze_room_upgrade(args, image_path)
    else:
        analyze_result = asyncio.run(analyze_room_upgrade_direct(args, image_path))
    save_json(output_dir / f"{run_id}_analyze.json", analyze_result)

    selected_products = analyze_result.get("selected_products", [])
    print_product_summary(analyze_result)
    if args.analyze_only:
        print("Analyze-only mode enabled. Skipping image generation.")
        return
    if not selected_products:
        print("No selected products returned. Stopping before image generation.")
        return

    print("[2/3] Generating after image with selected products...")
    if args.use_http:
        generate_result = generate_room_upgrade(args, image_path, analyze_result)
    else:
        generate_result = asyncio.run(
            generate_room_upgrade_direct(args, image_path, analyze_result)
        )
    save_json(output_dir / f"{run_id}_generate.json", generate_result)

    print("[3/3] Saving generated image...")
    after_image_url = generate_result.get("after_image_url")
    if not after_image_url:
        print("Generation completed but no image was returned.")
        return

    image_output = output_dir / f"{run_id}_after.png"
    save_generated_image(after_image_url, image_output)
    print(f"Saved after image: {image_output}")


def analyze_room_upgrade(args: argparse.Namespace, image_path: Path) -> Dict[str, Any]:
    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
    with httpx.Client(timeout=180) as client:
        with image_path.open("rb") as image_file:
            response = client.post(
                f"{args.base_url}/room-upgrade/analyze/upload",
                data={
                    "prompt": args.prompt,
                    "budget": str(args.budget),
                    "currency": args.currency,
                },
                files={"image": (image_path.name, image_file, mime_type)},
            )
    response.raise_for_status()
    return response.json()


async def analyze_room_upgrade_direct(
    args: argparse.Namespace,
    image_path: Path,
) -> Dict[str, Any]:
    from app.models.schemas import RoomUpgradeAnalyzeRequest
    from app.routers.room_upgrade import analyze_room_upgrade as analyze_handler

    request = RoomUpgradeAnalyzeRequest(
        image_base64=base64.b64encode(image_path.read_bytes()).decode("utf-8"),
        prompt=args.prompt,
        budget=args.budget,
        currency=args.currency,
    )
    result = await analyze_handler(request)
    return result.model_dump(mode="json")


def generate_room_upgrade(
    args: argparse.Namespace,
    image_path: Path,
    analyze_result: Dict[str, Any],
) -> Dict[str, Any]:
    image_base64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    payload = {
        "image_base64": image_base64,
        "prompt": args.prompt,
        "scene_analysis": analyze_result["scene_analysis"],
        "selected_products": analyze_result["selected_products"],
    }
    with httpx.Client(timeout=240) as client:
        response = client.post(
            f"{args.base_url}/room-upgrade/generate",
            json=payload,
        )
    response.raise_for_status()
    return response.json()


async def generate_room_upgrade_direct(
    args: argparse.Namespace,
    image_path: Path,
    analyze_result: Dict[str, Any],
) -> Dict[str, Any]:
    from app.models.schemas import RoomUpgradeGenerateRequest
    from app.routers.room_upgrade import generate_room_upgrade as generate_handler

    request = RoomUpgradeGenerateRequest(
        image_base64=base64.b64encode(image_path.read_bytes()).decode("utf-8"),
        prompt=args.prompt,
        scene_analysis=analyze_result["scene_analysis"],
        selected_products=analyze_result["selected_products"],
    )
    result = await generate_handler(request)
    return result.model_dump(mode="json")


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Saved JSON: {path}")


def save_generated_image(after_image_url: str, output_path: Path) -> None:
    if after_image_url.startswith("data:"):
        image_data = after_image_url.split(",", 1)[1]
        output_path.write_bytes(base64.b64decode(image_data))
        return

    with httpx.Client(timeout=120) as client:
        response = client.get(after_image_url)
        response.raise_for_status()
        output_path.write_bytes(response.content)


def print_product_summary(analyze_result: Dict[str, Any]) -> None:
    budget = analyze_result.get("budget", 0)
    total = analyze_result.get("total_estimated", 0)
    within_budget = analyze_result.get("within_budget", False)
    print(f"Budget: ${budget:.2f} | Selected total: ${total:.2f} | Within budget: {within_budget}")

    for index, selected in enumerate(analyze_result.get("selected_products", []), start=1):
        item = selected["shopping_list_item"]
        product = selected["chosen_product"]
        print(
            f"{index}. {item['item_name']}: {product['title']} "
            f"(${product['price']:.2f} at {product['store']})"
        )
        print(f"   Buy: {product['buy_link']}")


if __name__ == "__main__":
    main()
