import os
import asyncio
import base64
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query, Body
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import httpx

load_dotenv()

TEKMETRIC_BASE_URL = "https://shop.tekmetric.com/api/v1"
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SHOP_ID = int(os.getenv("TEKMETRIC_SHOP_ID", 0))

if not CLIENT_ID or not CLIENT_SECRET:
    raise RuntimeError("CLIENT_ID or CLIENT_SECRET not set")
if not SHOP_ID:
    raise RuntimeError("TEKMETRIC_SHOP_ID not set")

app = FastAPI(
    title="JJ Auto API",
    description="FastAPI-based AI Assistant for Tekmetric integration",
    version="1.0.0",
    servers=[{"url": "https://web-production-1dc1.up.railway.app"}]
)

class AppointmentCreate(BaseModel):
    customerId: int = Field(..., description="Tekmetric customer ID")
    vehicleId: int = Field(..., description="Tekmetric vehicle ID")
    startTime: str = Field(..., description="ISO-8601 datetime when appointment starts")
    endTime: str = Field(..., description="ISO-8601 datetime when appointment ends")
    title: Optional[str] = Field(None, description="Short title for the appointment")
    description: Optional[str] = Field(None, description="Longer description or notes")
    dropoffTime: Optional[str] = Field(None, description="ISO-8601 datetime for actual drop-off, if known")
    pickupTime: Optional[str] = Field(None, description="ISO-8601 datetime for actual pick-up, if known")
    rideOption: Optional[str] = Field(None, description="e.g. 'shuttle', 'loaner', etc.")

class AppointmentUpdate(BaseModel):
    startTime: Optional[str] = Field(None, description="ISO-8601 datetime when appointment starts")
    endTime: Optional[str] = Field(None, description="ISO-8601 datetime when appointment ends")
    title: Optional[str] = Field(None, description="Short title for the appointment")
    description: Optional[str] = Field(None, description="Longer description or notes")
    dropoffTime: Optional[str] = Field(None, description="ISO-8601 datetime for actual drop-off")
    pickupTime: Optional[str] = Field(None, description="ISO-8601 datetime for actual pick-up")
    rideOption: Optional[str] = Field(None, description="e.g. 'shuttle', 'loaner', etc.")


async def get_access_token() -> str:
    auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"grant_type": "client_credentials"}
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{TEKMETRIC_BASE_URL}/oauth/token", headers=headers, data=data)
        res.raise_for_status()
        return res.json()["access_token"]


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.get("/api/get_shops")
async def get_shops():
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/shops", headers=headers)
        res.raise_for_status()
        return res.json()


@app.get("/api/get_open_repair_orders")
async def get_open_repair_orders():
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

        async def hydrate_ro(ro):
            vehicle = "Unknown"
            customer = "Unknown"
            if ro.get("vehicleId"):
                try:
                    v_res = await client.get(
                        f"{TEKMETRIC_BASE_URL}/vehicles/{ro['vehicleId']}",
                        headers=headers
                    )
                    v_res.raise_for_status()
                    v = v_res.json()
                    vehicle = f"{v.get('year', '')} {v.get('make', '')} {v.get('model', '')}".strip()
                except:
                    pass
            if ro.get("customerId"):
                try:
                    c_res = await client.get(
                        f"{TEKMETRIC_BASE_URL}/customers/{ro['customerId']}",
                        headers=headers
                    )
                    c_res.raise_for_status()
                    c = c_res.json()
                    customer = f"{c.get('firstName', '')} {c.get('lastName', '')}".strip()
                except:
                    pass

            return {
                "id": ro.get("id"),
                "roNumber": ro.get("repairOrderNumber"),
                "vehicle": vehicle or "Unknown",
                "customer": customer or "Unknown",
                "status": ro.get("repairOrderStatus", {}).get("name", "Unknown"),
                "lastUpdated": ro.get("updatedDate")
            }

        return await asyncio.gather(*(hydrate_ro(ro) for ro in ros))


@app.get("/api/get_jobs_by_ro_number")
async def get_jobs_by_ro_number(ro_number: int):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {"shop": SHOP_ID, "repairOrderStatusId": [1, 2], "size": 100}
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/repair-orders", headers=headers, params=params)
        res.raise_for_status()
        ros = res.json().get("content", [])
        match = next((ro for ro in ros if ro.get("repairOrderNumber") == ro_number), None)
        if not match:
            raise HTTPException(status_code=404, detail=f"RO #{ro_number} not found")
        return await get_jobs_by_repair_order(match.get("id"))


@app.get("/api/get_jobs_by_ro")
async def get_jobs_by_repair_order(ro_id: int):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {"shop": SHOP_ID, "repairOrderId": ro_id, "size": 100}
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/jobs", headers=headers, params=params)
        res.raise_for_status()
        jobs = res.json().get("content", [])
        output = []
        for job in jobs:
            tech_name = "Unassigned"
            if job.get("technicianId"):
                try:
                    tech_res = await client.get(
                        f"{TEKMETRIC_BASE_URL}/employees/{job['technicianId']}",
                        headers=headers
                    )
                    tech_res.raise_for_status()
                    tech = tech_res.json()
                    tech_name = f"{tech.get('firstName', '')} {tech.get('lastName', '')}".strip()
                except:
                    pass
            output.append({
                "jobName": job.get("name"),
                "tech": tech_name,
                "note": job.get("note"),
                "authorized": job.get("authorized"),
                "laborTotal": job.get("laborTotal"),
                "partsTotal": job.get("partsTotal"),
                "status": "Complete" if job.get("archived") else "In Progress",
                "labor": job.get("labor", []),
                "parts": job.get("parts", [])
            })
        return {"repairOrderId": ro_id, "jobCount": len(output), "jobs": output}


@app.get("/api/get_customer")
async def get_customer(search: str):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {"shop": SHOP_ID, "search": search, "size": 10}
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/customers", headers=headers, params=params)
        res.raise_for_status()
        customers = res.json().get("content", [])
        results = []
        for c in customers:
            phone = c.get("phone", [])
            phone_str = phone[0]["number"] if phone else "N/A"
            results.append({
                "id": c.get("id"),
                "name": f"{c.get('firstName', '')} {c.get('lastName', '')}".strip(),
                "email": c.get("email", "N/A"),
                "phone": phone_str,
                "okForMarketing": c.get("okForMarketing"),
                "notes": c.get("notes", None),
                "address": c.get("address", {}).get("fullAddress", "N/A"),
                "created": c.get("createdDate"),
                "updated": c.get("updatedDate")
            })
        return {"query": search, "matchCount": len(results), "results": results}


@app.get("/api/get_customer_by_id")
async def get_customer_by_id(id: int):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        page = 0
        while True:
            params = {"shop": SHOP_ID, "size": 100, "page": page}
            res = await client.get(f"{TEKMETRIC_BASE_URL}/customers", headers=headers, params=params)
            res.raise_for_status()
            customers = res.json().get("content", [])
            if not customers:
                break
            for c in customers:
                if c.get("id") == id:
                    phone = c.get("phone", [])
                    phone_str = phone[0]["number"] if phone else "N/A"
                    return {
                        "id": c.get("id"),
                        "name": f"{c.get('firstName', '')} {c.get('lastName', '')}".strip(),
                        "email": c.get("email", "N/A"),
                        "phone": phone_str,
                        "okForMarketing": c.get("okForMarketing"),
                        "notes": c.get("notes", None),
                        "address": c.get("address", {}).get("fullAddress", "N/A"),
                        "customerType": c.get("customerType", {}).get("name"),
                        "created": c.get("createdDate"),
                        "updated": c.get("updatedDate")
                    }
            page += 1
        raise HTTPException(status_code=404, detail=f"Customer ID {id} not found")


@app.get("/api/get_full_customer_history")
async def get_full_customer_history(id: int):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        customer = None
        page = 0
        while True:
            params = {"shop": SHOP_ID, "size": 100, "page": page}
            res = await client.get(f"{TEKMETRIC_BASE_URL}/customers", headers=headers, params=params)
            res.raise_for_status()
            customers = res.json().get("content", [])
            if not customers:
                break
            for c in customers:
                if c.get("id") == id:
                    customer = c
                    break
            if customer:
                break
            page += 1

        if not customer:
            raise HTTPException(status_code=404, detail=f"Customer ID {id} not found")

        vehicle_params = {"shop": SHOP_ID, "customerId": id, "size": 100}
        vehicle_res = await client.get(f"{TEKMETRIC_BASE_URL}/vehicles", headers=headers, params=vehicle_params)
        vehicle_res.raise_for_status()
        vehicles = vehicle_res.json().get("content", [])

        async def get_ros_and_jobs(vehicle):
            ro_params = {"shop": SHOP_ID, "vehicleId": vehicle["id"], "size": 100}
            ro_res = await client.get(f"{TEKMETRIC_BASE_URL}/repair-orders", headers=headers, params=ro_params)
            ro_res.raise_for_status()
            ros = ro_res.json().get("content", [])

            async def get_jobs(ro):
                job_params = {"shop": SHOP_ID, "repairOrderId": ro["id"], "size": 100}
                job_res = await client.get(f"{TEKMETRIC_BASE_URL}/jobs", headers=headers, params=job_params)
                job_res.raise_for_status()
                jobs = job_res.json().get("content", [])
                return {
                    "roNumber": ro.get("repairOrderNumber"),
                    "status": ro.get("repairOrderStatus", {}).get("name"),
                    "jobs": [
                        {"jobName": j.get("name"), "techId": j.get("technicianId")}
                        for j in jobs
                    ]
                }

            jobs_nested = await asyncio.gather(*(get_jobs(ro) for ro in ros))
            return {
                "vehicleId": vehicle["id"],
                "year": vehicle.get("year"),
                "make": vehicle.get("make"),
                "model": vehicle.get("model"),
                "repairOrders": jobs_nested
            }

        vehicles_with_data = await asyncio.gather(*(get_ros_and_jobs(v) for v in vehicles))

        return {
            "customer": {
                "id": customer.get("id"),
                "name": f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip(),
                "email": customer.get("email", "N/A"),
                "phone": customer.get("phone", [{}])[0].get("number", "N/A"),
                "address": customer.get("address", {}).get("fullAddress", "N/A")
            },
            "vehicles": vehicles_with_data
        }


@app.get("/api/get_vehicles_by_customer")
async def get_vehicles_by_customer(customer_id: int):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {"shop": SHOP_ID, "customerId": customer_id, "size": 100}
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
        return simplified


@app.get("/api/get_vehicle")
async def get_vehicle(vehicle_id: int):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/vehicles/{vehicle_id}", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Vehicle ID {vehicle_id} not found")
        res.raise_for_status()
        return res.json()


@app.get("/api/get_service_by_vehicle")
async def get_service_by_vehicle(
    vehicle_id: int,
    year: Optional[int] = Query(None, description="YYYY to filter ROs")
):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {"shop": SHOP_ID, "vehicleId": vehicle_id, "size": 100}
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/repair-orders", headers=headers, params=params)
        res.raise_for_status()
        ros = res.json().get("content", [])
        filtered = []
        for ro in ros:
            created = ro.get("createdDate", "")
            if year and not created.startswith(str(year)):
                continue
            filtered.append({
                "roNumber": ro.get("repairOrderNumber"),
                "status": ro.get("repairOrderStatus", {}).get("name", "Unknown"),
                "createdDate": created
            })
        return filtered


@app.get("/api/get_appointments")
async def get_appointments(
    start: str = Query(..., description="Start date/time in ISO format (e.g. 2025-06-10T09:00:00Z)"),
    end: str = Query(..., description="End date/time in ISO format")
):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {"shop": SHOP_ID, "start": start, "end": end}
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/appointments", headers=headers, params=params)
        res.raise_for_status()
        return res.json().get("content", [])


@app.get("/api/get_appointment")
async def get_appointment(appointment_id: int):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/appointments/{appointment_id}", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Appointment ID {appointment_id} not found")
        res.raise_for_status()
        return res.json()


@app.post("/api/create_appointment")
async def create_appointment(payload: AppointmentCreate):
    token = await get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = payload.dict()
    data["shopId"] = SHOP_ID
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{TEKMETRIC_BASE_URL}/appointments", headers=headers, json=data)
        if res.status_code >= 400:
            raise HTTPException(status_code=res.status_code, detail=res.text)
        return res.json()


@app.patch("/api/update_appointment")
async def update_appointment(
    appointment_id: int = Query(..., description="ID of appointment to update"),
    payload: AppointmentUpdate = Body(..., description="Fields to update")
):
    token = await get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = payload.dict(exclude_unset=True)
    async with httpx.AsyncClient() as client:
        res = await client.patch(f"{TEKMETRIC_BASE_URL}/appointments/{appointment_id}", headers=headers, json=data)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Appointment ID {appointment_id} not found")
        res.raise_for_status()
        return res.json()


@app.delete("/api/delete_appointment")
async def delete_appointment(
    appointment_id: int = Query(..., description="ID of appointment to delete")
):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        res = await client.delete(f"{TEKMETRIC_BASE_URL}/appointments/{appointment_id}", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Appointment ID {appointment_id} not found")
        res.raise_for_status()
        return {"detail": f"Appointment {appointment_id} deleted successfully"}
