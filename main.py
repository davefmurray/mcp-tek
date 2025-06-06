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
    servers=[
        {"url": "https://web-production-1dc1.up.railway.app"}
    ]
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
        "repairOrderStatusId": [1, 2],  # Estimate + Work-In-Progress
        "size": 100
    }

    async with httpx.AsyncClient() as client:
        try:
            ro_res = await client.get(f"{TEKMETRIC_BASE_URL}/repair-orders", headers=headers, params=params)
            ro_res.raise_for_status()
            ros = ro_res.json().get("content", [])
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

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
                "roNumber": ro.get("repairOrderNumber"),
                "vehicle": vehicle or "Unknown",
                "customer": customer or "Unknown",
                "status": ro.get("repairOrderStatus", {}).get("name", "Unknown"),
                "lastUpdated": ro.get("updatedDate")
            }

        return await asyncio.gather(*(hydrate_ro(ro) for ro in ros))
