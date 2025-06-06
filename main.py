import os
import asyncio
import base64
from fastapi import FastAPI, HTTPException
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

async def get_access_token():
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
                    v_res = await client.get(f"{TEKMETRIC_BASE_URL}/vehicles/{ro['vehicleId']}", headers=headers)
                    v_res.raise_for_status()
                    v = v_res.json()
                    vehicle = f"{v.get('year', '')} {v.get('make', '')} {v.get('model', '')}".strip()
                except:
                    pass
            if ro.get("customerId"):
                try:
                    c_res = await client.get(f"{TEKMETRIC_BASE_URL}/customers/{ro['customerId']}", headers=headers)
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
                    tech_res = await client.get(f"{TEKMETRIC_BASE_URL}/employees/{job['technicianId']}", headers=headers)
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
