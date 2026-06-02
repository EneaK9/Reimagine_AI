#!/usr/bin/env python3
"""
Interactive Product Searcher CLI.

Run from the backend directory:
    ./scripts/product_searcher.py
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Optional


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models.schemas import ProductResult, StoreName
from app.services.product_search_service import product_search_service


DEFAULT_STORES = [
    StoreName.AMAZON,
    StoreName.TARGET,
    StoreName.EBAY,
    StoreName.IKEA,
]
MAX_RESULTS_PER_STORE = 10
MAX_TOTAL_RESULTS = 10


def main() -> int:
    print("Product Searcher")
    print("Search Amazon, Target, eBay, and IKEA from one description.")
    print("Include budget in the description if needed, for example: Tall yellow vase under $150\n")

    description = _prompt_required("Description: ")

    try:
        results, errors = asyncio.run(
            product_search_service.search_products(
                description=description,
                stores=DEFAULT_STORES,
                limit_per_store=MAX_RESULTS_PER_STORE,
            )
        )
    except ValueError as exc:
        print(f"\nConfiguration error: {exc}")
        print("Add SERP_API_KEY to backend/.env, then run this script again.")
        return 1
    except KeyboardInterrupt:
        print("\nSearch cancelled.")
        return 130
    except Exception as exc:
        print(f"\nSearch failed: {exc}")
        return 1

    _print_results(description, _select_display_results(results), errors)
    return 0


def _prompt_required(label: str) -> str:
    while True:
        value = input(label).strip()
        if value:
            return value
        print("Please enter a description.")


def _print_results(
    query: str,
    results: List[ProductResult],
    errors: List[str],
) -> None:
    print(f"\nQuery: {query}")

    if errors:
        print("\nStore errors:")
        for error in errors:
            print(f"- {error}")

    if not results:
        print("\nNo product results found.")
        return

    print(f"\nShowing top {len(results)} result(s):")
    for index, product in enumerate(results, start=1):
        print(f"\n{index}. {product.title}")
        print(f"   Store: {_format_store(product.store)}")
        print(f"   Price: {_format_price(product.price, product.currency)}")
        print(f"   Rating: {_format_optional(product.rating)}")
        print(f"   Reviews: {_format_optional(product.reviews)}")
        print(f"   Description: {_format_text(product.description)}")
        print(f"   Source: {product.source}")
        print(f"   Score: {product.score:.3f}")
        print(f"   Link: {product.link}")
        print(f"   Image: {_format_text(product.image)}")


def _select_display_results(results: List[ProductResult]) -> List[ProductResult]:
    by_store = {store: [] for store in DEFAULT_STORES}
    for product in results:
        by_store[product.store].append(product)

    selected = []
    while len(selected) < MAX_TOTAL_RESULTS:
        added_this_round = False
        for store in DEFAULT_STORES:
            if by_store[store]:
                selected.append(by_store[store].pop(0))
                added_this_round = True
                if len(selected) >= MAX_TOTAL_RESULTS:
                    break

        if not added_this_round:
            break

    return selected


def _format_store(store: StoreName) -> str:
    return store.value.replace("_", " ").title()


def _format_price(price: Optional[float], currency: str) -> str:
    if price is None:
        return "Not available"

    if currency == "USD":
        return f"${price:,.2f}"

    return f"{price:,.2f} {currency}"


def _format_optional(value: Optional[float]) -> str:
    if value is None:
        return "Not available"
    return str(value)


def _format_text(value: Optional[str]) -> str:
    if not value:
        return "Not available"
    return " ".join(value.split())


if __name__ == "__main__":
    raise SystemExit(main())
