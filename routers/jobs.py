from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel, Field
import httpx
from main import get_access_token, TEKMETRIC_BASE_URL, SHOP_ID

router = APIRouter()

class JobCreate(BaseModel):
    """
    Fields to create a new Job under an existing Repair Order.
    Tekmetric endpoint: POST /api/v1/jobs
    """
    repairOrderId: int = Field(..., description="Existing Repair Order ID")
    name: str = Field(..., description="Job name or description")
    jobCategoryName: Optional[str] = Field(None, description="Category (optional)")
    technicianId: Optional[int] = Field(None, description="Employee ID for tech")
    note: Optional[str] = Field(None, description="Any job-specific notes")

class JobUpdate(BaseModel):
    """
    Fields to update an existing Job.
    Tekmetric endpoint: PATCH /api/v1/jobs/{id}
    """
    name: Optional[str] = Field(None, description="Updated job name")
    authorized: Optional[bool] = Field(None, description="Authorized by customer")
    technicianId: Optional[int] = Field(None, description="Re-assign technician by ID")
    note: Optional[str] = Field(None, description="Update job note")
    partsTotal: Optional[int] = Field(None, description="Parts total in cents")
    laborTotal: Optional[int] = Field(None, description="Labor total in cents")
    archived: Optional[bool] = Field(None, description="Archive (decline) job")

@router.get("/", summary="List Jobs by Repair Order")
async def list_jobs_by_ro(repairOrderId: int = Query(..., description="Repair Order ID")):
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
    Returns a single Job by ID.
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

@router.post("/", summary="Create Job")
async def create_job(job: JobCreate):
    """
    Creates a new Job under a specified Repair Order.
    Tekmetric endpoint: POST /api/v1/jobs
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = job.dict()
    payload["shopId"] = SHOP_ID

    async with httpx.AsyncClient() as client:
        res = await client.post(f"{TEKMETRIC_BASE_URL}/jobs", headers=headers, json=payload)
        res.raise_for_status()
        return res.json()

@router.patch("/{job_id}", summary="Update Job")
async def update_job(job_id: int, job: JobUpdate):
    """
    Updates fields on an existing Job.
    Tekmetric endpoint: PATCH /api/v1/jobs/{id}
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = job.dict(exclude_unset=True)

    async with httpx.AsyncClient() as client:
        # Check if job exists
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