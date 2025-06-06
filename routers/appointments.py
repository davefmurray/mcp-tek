from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pydantic import BaseModel
import httpx
from main import get_access_token, TEKMETRIC_BASE_URL, SHOP_ID

router = APIRouter()

class AppointmentBase(BaseModel):
    customerId: Optional[int] = None
    vehicleId: Optional[int] = None
    startTime: Optional[str] = None
    endTime: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    dropoffTime: Optional[str] = None
    pickupTime: Optional[str] = None
    rideOption: Optional[str] = None

class AppointmentCreate(AppointmentBase):
    startTime: str
    endTime: str
    title: str

class AppointmentUpdate(AppointmentBase):
    pass

@router.get("/", summary="List Appointments")
async def list_appointments(
    customerId: Optional[int] = Query(None, description="Filter by customer ID"),
    vehicleId: Optional[int] = Query(None, description="Filter by vehicle ID"),
    start: Optional[str] = Query(None, description="Filter by start date (ISO 8601)"),
    end: Optional[str] = Query(None, description="Filter by end date (ISO 8601)"),
    updatedDateStart: Optional[str] = Query(None, description="Filter by updated date start (ISO 8601)"),
    updatedDateEnd: Optional[str] = Query(None, description="Filter by updated date end (ISO 8601)"),
    includeDeleted: bool = Query(True, description="Include deleted appointments"),
    sort: Optional[str] = Query(None, description="Field to sort by"),
    sortDirection: Optional[str] = Query(None, description="Sort direction: ASC or DESC"),
    size: int = Query(100, description="Number of results per page"),
    page: int = Query(0, description="Page number"),
):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "shop": SHOP_ID,
        "customerId": customerId,
        "vehicleId": vehicleId,
        "start": start,
        "end": end,
        "updatedDateStart": updatedDateStart,
        "updatedDateEnd": updatedDateEnd,
        "includeDeleted": includeDeleted,
        "sort": sort,
        "sortDirection": sortDirection,
        "size": size,
        "page": page,
    }
    params = {k: v for k, v in params.items() if v is not None}

    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/appointments", headers=headers, params=params)
        res.raise_for_status()
        return {"appointments": res.json().get("content", [])}

@router.get("/{appointment_id}", summary="Get Appointment by ID")
async def get_appointment(appointment_id: int):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/appointments/{appointment_id}", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Appointment ID {appointment_id} not found")
        res.raise_for_status()
        return res.json()

@router.post("/", summary="Create Appointment")
async def create_appointment(appointment: AppointmentCreate):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = appointment.dict()
    payload["shopId"] = SHOP_ID
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{TEKMETRIC_BASE_URL}/appointments", headers=headers, json=payload)
        res.raise_for_status()
        return res.json()

@router.patch("/{appointment_id}", summary="Update Appointment")
async def update_appointment(appointment_id: int, appointment: AppointmentUpdate):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = appointment.dict(exclude_unset=True)
    payload["shopId"] = SHOP_ID
    async with httpx.AsyncClient() as client:
        res = await client.patch(f"{TEKMETRIC_BASE_URL}/appointments/{appointment_id}", headers=headers, json=payload)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Appointment ID {appointment_id} not found")
        res.raise_for_status()
        return res.json()

@router.delete("/{appointment_id}", summary="Delete Appointment")
async def delete_appointment(appointment_id: int):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        res = await client.delete(f"{TEKMETRIC_BASE_URL}/appointments/{appointment_id}", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Appointment ID {appointment_id} not found")
        res.raise_for_status()
        return res.json()