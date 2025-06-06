from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel, Field
import httpx
from main import get_access_token, TEKMETRIC_BASE_URL, SHOP_ID
import asyncio

router = APIRouter()

class RepairOrderCreate(BaseModel):
    customerId: int = Field(..., description="Existing Tekmetric Customer ID")
    vehicleId:  int = Field(..., description="Existing Tekmetric Vehicle ID")
    technicianId: Optional[int] = Field(None, description="Employee ID assigned to technician")
    serviceWriterId: Optional[int] = Field(None, description="Employee ID assigned as service writer")
    appointmentStartTime: Optional[str] = Field(
        None, description="ISO-8601 timestamp for appointment start"
    )
    notes: Optional[str] = Field(None, description="Any notes on the repair order")

class RepairOrderUpdate(BaseModel):
    keyTag:          Optional[str] = Field(None, description="KeyTag label")
    milesIn:         Optional[int] = Field(None, description="Mileage in on RO")
    milesOut:        Optional[int] = Field(None, description="Mileage out on RO")
    technicianId:    Optional[int] = Field(None, description="Assign technician by employee ID")
    serviceWriterId: Optional[int] = Field(None, description="Assign service writer by employee ID")
    customerTimeOut: Optional[str] = Field(None, description="Promise time (ISO-8601)")

@router.get("/open", summary="List Open Repair Orders")
async def list_open_repair_orders():
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "shop": SHOP_ID,
        "repairOrderStatusId": [1, 2],
        "size": 100
    }
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/repair-orders", headers=headers, params=params)
        res.raise_for_status()
        ros = res.json().get("content", [])

        async def hydrate(ro: dict):
            vehicle_str = "Unknown"
            if ro.get("vehicleId"):
                try:
                    v_res = await client.get(
                        f"{TEKMETRIC_BASE_URL}/vehicles/{ro['vehicleId']}", headers=headers
                    )
                    v_res.raise_for_status()
                    v = v_res.json()
                    vehicle_str = f"{v.get('year','')} {v.get('make','')} {v.get('model','')}".strip()
                except:
                    pass
            customer_str = "Unknown"
            if ro.get("customerId"):
                try:
                    c_res = await client.get(
                        f"{TEKMETRIC_BASE_URL}/customers/{ro['customerId']}", headers=headers
                    )
                    c_res.raise_for_status()
                    c = c_res.json()
                    customer_str = f"{c.get('firstName','')} {c.get('lastName','')}".strip()
                except:
                    pass
            return {
                "id": ro.get("id"),
                "roNumber": ro.get("repairOrderNumber"),
                "vehicle": vehicle_str or "Unknown",
                "customer": customer_str or "Unknown",
                "status": ro.get("repairOrderStatus", {}).get("name", "Unknown"),
                "lastUpdated": ro.get("updatedDate")
            }

        return await asyncio.gather(*(hydrate(ro) for ro in ros))

@router.get("/{ro_id}", summary="Get Repair Order by ID")
async def get_repair_order(ro_id: int):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/repair-orders/{ro_id}", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"RO ID {ro_id} not found")
        res.raise_for_status()
        return res.json()

@router.post("/", summary="Create Repair Order")
async def create_repair_order(payload: RepairOrderCreate):
    token = await get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = payload.dict()
    data["shopId"] = SHOP_ID
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{TEKMETRIC_BASE_URL}/repair-orders", headers=headers, json=data)
        res.raise_for_status()
        return res.json()

@router.patch("/{ro_id}", summary="Update Repair Order")
async def update_repair_order(ro_id: int, payload: RepairOrderUpdate):
    token = await get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = payload.dict(exclude_unset=True)
    async with httpx.AsyncClient() as client:
        check = await client.get(f"{TEKMETRIC_BASE_URL}/repair-orders/{ro_id}", headers=headers)
        if check.status_code == 404:
            raise HTTPException(status_code=404, detail=f"RO ID {ro_id} not found")
        res = await client.patch(f"{TEKMETRIC_BASE_URL}/repair-orders/{ro_id}", headers=headers, json=data)
        res.raise_for_status()
        return res.json()

@router.delete("/{ro_id}", summary="Delete Repair Order")
async def delete_repair_order(ro_id: int):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        res = await client.delete(f"{TEKMETRIC_BASE_URL}/repair-orders/{ro_id}", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"RO ID {ro_id} not found")
        res.raise_for_status()
        return {"detail": f"Repair Order {ro_id} deleted"}