from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import httpx
from main import get_access_token, TEKMETRIC_BASE_URL, SHOP_ID

router = APIRouter()

@router.get("/", summary="List Employees")
async def list_employees(
    search: Optional[str] = Query(None, description="Search by name"),
    updatedDateStart: Optional[str] = Query(None, description="Filter by updated date start (ISO 8601)"),
    updatedDateEnd: Optional[str] = Query(None, description="Filter by updated date end (ISO 8601)"),
    sort: Optional[str] = Query(None, description="Field to sort by"),
    sortDirection: Optional[str] = Query(None, description="Sort direction: ASC or DESC"),
    size: int = Query(100, description="Number of results per page"),
    page: int = Query(0, description="Page number"),
):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "shop": SHOP_ID,
        "search": search,
        "updatedDateStart": updatedDateStart,
        "updatedDateEnd": updatedDateEnd,
        "sort": sort,
        "sortDirection": sortDirection,
        "size": size,
        "page": page,
    }
    # Remove None values from params
    params = {k: v for k, v in params.items() if v is not None}

    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/employees", headers=headers, params=params)
        res.raise_for_status()
        return {"employees": res.json().get("content", [])}

@router.get("/{employee_id}", summary="Get Employee by ID")
async def get_employee(employee_id: int):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/employees/{employee_id}", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Employee ID {employee_id} not found")
        res.raise_for_status()
        return res.json()