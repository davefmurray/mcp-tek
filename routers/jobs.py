from fastapi import APIRouter, HTTPException, Query
from typing import List, Any
from pydantic import BaseModel
import httpx
from main import get_access_token, TEKMETRIC_BASE_URL, SHOP_ID

router = APIRouter()

class JobUpdate(BaseModel):
    # Allow arbitrary fields for update payload
    class Config:
        extra = "allow"

@router.get("/", summary="List Jobs by Repair Order")
async def list_jobs(repairOrderId: int = Query(..., description="Filter by Repair Order ID")):
    """
    Returns all jobs for a given Repair Order.
    Tekmetric endpoint: GET /api/v1/jobs?shop={shop}&repairOrderId={id}&size=100
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {"shop": SHOP_ID, "repairOrderId": repairOrderId, "size": 100}

    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/jobs", headers=headers, params=params)
        res.raise_for_status()
        return {"jobs": res.json().get("content", [])}

@router.get("/{job_id}", summary="Get Job by ID")
async def get_job(job_id: int):
    """
    Get a single Job by ID.
    Tekmetric endpoint: GET /api/v1/jobs/{id}
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/jobs/{job_id}", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Job ID {job_id} not found")
        res.raise_for_status()
        return res.json()

@router.patch("/{job_id}", summary="Update Job")
async def update_job(job_id: int, job: JobUpdate):
    """
    Update fields on an existing Job.
    Tekmetric endpoint: PATCH /api/v1/jobs/{id}
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = job.dict(exclude_unset=True)

    async with httpx.AsyncClient() as client:
        # Check existence first
        check = await client.get(f"{TEKMETRIC_BASE_URL}/jobs/{job_id}", headers=headers)
        if check.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Job ID {job_id} not found")
        res = await client.patch(f"{TEKMETRIC_BASE_URL}/jobs/{job_id}", headers=headers, json=payload)
        res.raise_for_status()
        return res.json()

@router.delete("/{job_id}", summary="Delete Job")
async def delete_job(job_id: int):
    """
    Deletes (archives) a Job.
    Tekmetric endpoint: DELETE /api/v1/jobs/{id}
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        res = await client.delete(f"{TEKMETRIC_BASE_URL}/jobs/{job_id}", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Job ID {job_id} not found")
        res.raise_for_status()
        return {"detail": f"Job {job_id} deleted"}
