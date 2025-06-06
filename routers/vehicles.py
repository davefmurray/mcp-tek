from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel, Field
import httpx
from main import get_access_token, TEKMETRIC_BASE_URL, SHOP_ID

router = APIRouter()

class VehicleCreate(BaseModel):
    customerId: int = Field(..., description="Existing Customer ID for this vehicle")
    year: int = Field(..., description="Year of the vehicle")
    make: str = Field(..., description="Make (e.g., 'Ford')")
    model: str = Field(..., description="Model (e.g., 'Escape')")
    subModel: Optional[str] = Field(None, description="Submodel (optional)")
    engine: Optional[str] = Field(None, description="Engine spec (optional)")
    color: Optional[str] = Field(None, description="Color (optional)")
    licensePlate: Optional[str] = Field(None, description="License plate (optional)")
    state: Optional[str] = Field(None, description="State of registration (optional)")
    vin: Optional[str] = Field(None, description="Vehicle VIN (optional)")
    driveType: Optional[str] = Field(None, description="Drive type")
    transmission: Optional[str] = Field(None, description="Transmission")
    bodyType: Optional[str] = Field(None, description="Body type")
    notes: Optional[str] = Field(None, description="Any notes")
    unitNumber: Optional[str] = Field(None, description="Unit number")

class VehicleUpdate(BaseModel):
    year: Optional[int] = Field(None, description="Year of the vehicle")
    make: Optional[str] = Field(None, description="Make")
    model: Optional[str] = Field(None, description="Model")
    subModel: Optional[str] = Field(None, description="Submodel")
    engine: Optional[str] = Field(None, description="Engine details")
    color: Optional[str] = Field(None, description="Color")
    licensePlate: Optional[str] = Field(None, description="License plate")
    state: Optional[str] = Field(None, description="Plate state")
    vin: Optional[str] = Field(None, description="VIN")
    driveType: Optional[str] = Field(None, description="Drive type")
    transmission: Optional[str] = Field(None, description="Transmission")
    bodyType: Optional[str] = Field(None, description="Body type")
    notes: Optional[str] = Field(None, description="Any notes")
    unitNumber: Optional[str] = Field(None, description="Unit number")

@router.get("/", summary="List Vehicles by Customer")
async def list_vehicles_by_customer(customerId: int = Query(..., description="Filter by customer ID")):
    """
    Returns all vehicles for a given customer.
    Tekmetric endpoint: GET /api/v1/vehicles?shop={shop}&customerId={id}&size=100
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {"shop": SHOP_ID, "customerId": customerId, "size": 100}

    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/vehicles", headers=headers, params=params)
        res.raise_for_status()
        vehicles = res.json().get("content", [])
        simplified = []
        for v in vehicles:
            simplified.append({
                "vehicleId": v.get("id"),
                "year": v.get("year"),
                "make": v.get("make"),
                "model": v.get("model"),
                "vin": v.get("vin", "N/A"),
                "licensePlate": v.get("licensePlate", "N/A")
            })
        return {"vehicles": simplified}

@router.get("/{vehicle_id}", summary="Get Vehicle by ID")
async def get_vehicle(vehicle_id: int):
    """
    Returns a single Vehicle by ID.
    Tekmetric endpoint: GET /api/v1/vehicles/{id}
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/vehicles/{vehicle_id}", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Vehicle ID {vehicle_id} not found")
        res.raise_for_status()
        return res.json()

@router.post("/", summary="Create Vehicle")
async def create_vehicle(vehicle: VehicleCreate):
    """
    Creates a new Vehicle under a specified customer.
    Tekmetric endpoint: POST /api/v1/vehicles
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = vehicle.dict()
    payload["shopId"] = SHOP_ID

    async with httpx.AsyncClient() as client:
        res = await client.post(f"{TEKMETRIC_BASE_URL}/vehicles", headers=headers, json=payload)
        res.raise_for_status()
        return res.json()

@router.patch("/{vehicle_id}", summary="Update Vehicle")
async def update_vehicle(vehicle_id: int, vehicle: VehicleUpdate):
    """
    Updates fields on an existing Vehicle.
    Tekmetric endpoint: PATCH /api/v1/vehicles/{id}
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = vehicle.dict(exclude_unset=True)

    async with httpx.AsyncClient() as client:
        # Check if vehicle exists
        check = await client.get(f"{TEKMETRIC_BASE_URL}/vehicles/{vehicle_id}", headers=headers)
        if check.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Vehicle ID {vehicle_id} not found")
        payload["shopId"] = SHOP_ID
        res = await client.patch(f"{TEKMETRIC_BASE_URL}/vehicles/{vehicle_id}", headers=headers, json=payload)
        res.raise_for_status()
        return res.json()

@router.delete("/{vehicle_id}", summary="Delete Vehicle")
async def delete_vehicle(vehicle_id: int):
    """
    Deletes (archives) a Vehicle.
    Tekmetric endpoint: DELETE /api/v1/vehicles/{id}
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        res = await client.delete(f"{TEKMETRIC_BASE_URL}/vehicles/{vehicle_id}", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Vehicle ID {vehicle_id} not found")
        res.raise_for_status()
        return {"detail": f"Vehicle {vehicle_id} deleted successfully"}