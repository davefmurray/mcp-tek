from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import httpx
from main import get_access_token, TEKMETRIC_BASE_URL, SHOP_ID

router = APIRouter()

@router.get("/", summary="List Inventory Parts")
async def list_inventory(
    partTypeId: int = Query(..., description="Part type ID (1=Part, 2=Tire, 5=Battery)"),
    partNumbers: Optional[List[str]] = Query(None, description="Exact part numbers to filter"),
    width: Optional[str] = Query(None, description="Tire width (for tires only)"),
    ratio: Optional[float] = Query(None, description="Tire ratio (for tires only)"),
    diameter: Optional[float] = Query(None, description="Tire diameter (for tires only)"),
    tireSize: Optional[str] = Query(None, description="Concatenated tire size (width/ratio/diameter)"),
    sort: Optional[str] = Query(None, description="Field(s) to sort by (id, name, brand, partNumber)"),
    sortDirection: Optional[str] = Query(None, description="Sort direction: ASC or DESC"),
    size: int = Query(100, description="Results per page (max 100)"),
    page: int = Query(0, description="Page number"),
):
    """
    Returns a list of inventory parts filtered by provided parameters.
    Tekmetric endpoint: GET /api/v1/inventory
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "shop": SHOP_ID,
        "partTypeId": partTypeId,
        "partNumbers": partNumbers,
        "width": width,
        "ratio": ratio,
        "diameter": diameter,
        "tireSize": tireSize,
        "sort": sort,
        "sortDirection": sortDirection,
        "size": size,
        "page": page,
    }
    # Remove None values
    params = {k: v for k, v in params.items() if v is not None}

    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/inventory", headers=headers, params=params)
        res.raise_for_status()
        data = res.json()
        return {"inventory": data.get("content", []), "pageable": data.get("pageable", {})}