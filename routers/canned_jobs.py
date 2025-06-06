from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional
import httpx
from main import get_access_token, TEKMETRIC_BASE_URL, SHOP_ID

router = APIRouter()

@router.get("/", summary="List Canned Jobs")
async def list_canned_jobs(
    search: Optional[str] = Query(None, description="Filter by job name"),
    categories: Optional[List[str]] = Query(None, description="Filter by job category codes"),
    rates: Optional[List[str]] = Query(None, description="Filter by labor rates"),
    sort: Optional[str] = Query(None, description="Field to sort by"),
    sortDirection: Optional[str] = Query(None, description="Sort direction: ASC or DESC"),
    size: int = Query(100, description="Number of results per page"),
    page: int = Query(0, description="Page number"),
):
    """
    Returns a list of all canned jobs filtered by the provided search parameters.
    Tekmetric endpoint: GET /api/v1/canned-jobs
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "shop": SHOP_ID,
        "search": search,
        "categories": categories,
        "rates": rates,
        "sort": sort,
        "sortDirection": sortDirection,
        "size": size,
        "page": page,
    }
    # Remove None params
    params = {k: v for k, v in params.items() if v is not None}

    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/canned-jobs", headers=headers, params=params)
        res.raise_for_status()
        return {"cannedJobs": res.json().get("content", [])}

@router.post("/repair_orders/{ro_id}", summary="Add Canned Jobs to Repair Order")
async def add_canned_jobs_to_repair_order(
    ro_id: int,
    job_ids: List[int] = Body(..., description="List of canned job IDs to add")
):
    """
    Adds given canned jobs to a repair order.
    Tekmetric endpoint: POST /api/v1/repair-orders/{id}/canned-jobs
    """
    token = await get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        # Validate the repair order exists
        ro_res = await client.get(f"{TEKMETRIC_BASE_URL}/repair-orders/{ro_id}", headers=headers)
        if ro_res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Repair Order ID {ro_id} not found")
        # Add the canned jobs
        res = await client.post(
            f"{TEKMETRIC_BASE_URL}/repair-orders/{ro_id}/canned-jobs",
            headers=headers,
            json=job_ids
        )
        res.raise_for_status()
        return res.json()