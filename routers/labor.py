from fastapi import APIRouter, HTTPException, Body
import httpx
from main import get_access_token, TEKMETRIC_BASE_URL

router = APIRouter()

@router.patch("/{labor_id}", summary="Update Labor Technician")
async def update_labor(
    labor_id: int,
    technicianId: int = Body(..., description="Employee ID of the technician")
):
    token = await get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {"technicianId": technicianId}
    async with httpx.AsyncClient() as client:
        res = await client.patch(
            f"{TEKMETRIC_BASE_URL}/labor/{labor_id}",
            headers=headers,
            json=payload
        )
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Labor ID {labor_id} not found")
        res.raise_for_status()
        return res.json()