"""
ReimagineAI - Products Router
Handles product search endpoints for shopping recommendations.
"""
from fastapi import APIRouter, HTTPException

from ..models.schemas import ProductSearchRequest, ProductSearchResponse
from ..services.product_search_service import product_search_service


router = APIRouter(prefix="/products", tags=["Products"])


@router.post("/search", response_model=ProductSearchResponse)
async def search_products(request: ProductSearchRequest):
    """
    Search supported retailers for products matching a natural-language description.
    """
    try:
        results, errors = await product_search_service.search_products(
            description=request.description,
            stores=request.stores,
            limit_per_store=request.limit_per_store,
        )

        return ProductSearchResponse(
            query=request.description,
            results=results,
            errors=errors,
        )
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
