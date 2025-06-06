from fastapi import APIRouter, HTTPException, Body
from typing import Optional
import httpx
from main import get_access_token, TEKMETRIC_BASE_URL

router = APIRouter()

@router.put("/{job_id}/job-clock", summary="Update Job Clock")
async def update_job_clock(
    job_id: int,
    technicianId: int = Body(..., description="Employee ID of the technician"),
    loggedHours: float = Body(..., description="Hours logged on job by employee")
):
    token = await get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {"technicianId": technicianId, "loggedHours": loggedHours}
    async with httpx.AsyncClient() as client:
        res = await client.put(
            f"{TEKMETRIC_BASE_URL}/jobs/{job_id}/job-clock",
            headers=headers,
            json=payload
        )
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Job ID {job_id} not found")
        res.raise_for_status()
        return res.json()