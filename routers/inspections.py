from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import httpx
from main import get_access_token, TEKMETRIC_BASE_URL, SHOP_ID

router = APIRouter()

@router.get("/", summary="List Digital Vehicle Inspections (DVIs)")
async def list_inspections(
    startDate: Optional[str] = Query(None, description="Filter by inspection start date (ISO 8601)"),
    endDate: Optional[str] = Query(None, description="Filter by inspection end date (ISO 8601)"),
    vehicleId: Optional[int] = Query(None, description="Filter by vehicle ID"),
    repairOrderId: Optional[int] = Query(None, description="Filter by repair order ID"),
    sort: Optional[str] = Query(None, description="Sort fields (comma-separated)"),
    sortDirection: Optional[str] = Query(None, description="Sort direction: ASC or DESC"),
    size: int = Query(100, description="Results per page (max 100)"),
    page: int = Query(0, description="Page number"),
):
    """
    Retrieve a list of Digital Vehicle Inspections (DVIs) for this shop.
    Tekmetric endpoint: GET /api/v1/inspections
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "shop": SHOP_ID,
        "startDate": startDate,
        "endDate": endDate,
        "vehicleId": vehicleId,
        "repairOrderId": repairOrderId,
        "sort": sort,
        "sortDirection": sortDirection,
        "size": size,
        "page": page,
    }
    # Remove None values
    params = {k: v for k, v in params.items() if v is not None}

    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/inspections", headers=headers, params=params)
        res.raise_for_status()
        data = res.json()
        return {
            "inspections": data.get("content", []),
            "pageable": data.get("pageable", {})
        }

@router.get("/{inspection_id}", summary="Get Inspection by ID")
async def get_inspection(
    inspection_id: int,
    # shop is implicitly from environment
):
    """
    Retrieve detailed information for a specific inspection.
    Tekmetric endpoint: GET /api/v1/inspections/{id}
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {"shop": SHOP_ID}

    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/inspections/{inspection_id}", headers=headers, params=params)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Inspection ID {inspection_id} not found")
        res.raise_for_status()
        return res.json()