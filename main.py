from fastapi import FastAPI
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import os
import httpx
import base64
import json
import logging

# Load .env
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tekmetric")

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

app = FastAPI(
    title="Tekmetric API",
    version="1.0.0",
    servers=[{"url": "https://web-production-1dc1.up.railway.app"}]
)

# 🔐 Auth helper
async def get_access_token() -> str | None:
    logger.info("🔐 Getting Tekmetric access token")
    if not CLIENT_ID or not CLIENT_SECRET:
        logger.error("❌ Missing CLIENT_ID or CLIENT_SECRET")
        return None

    encoded = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
    }
    data = {"grant_type": "client_credentials"}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                "https://shop.tekmetric.com/api/v1/oauth/token",
                data=data,
                headers=headers
            )
            logger.info(f"🔑 Token response status: {resp.status_code}")
            logger.info(f"🔑 Token body: {await resp.aread()}")
            resp.raise_for_status()
            return resp.json().get("access_token")
        except Exception as e:
            logger.exception("❌ Token fetch failed")
            return None

# ✅ /api/get_shops
@app.get("/api/get_shops", summary="Get Shops")
async def get_shops():
    token = await get_access_token()
    if not token:
        return JSONResponse(content={"error": "Unable to authenticate"}, status_code=401)

    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get("https://shop.tekmetric.com/api/v1/shops", headers=headers)
            logger.info(f"📦 Shops response status: {resp.status_code}")
            data = resp.json()
            return JSONResponse(content=data)
        except Exception as e:
            logger.exception("❌ Failed to fetch shops")
            return JSONResponse(content={"error": str(e)}, status_code=500)

# ✅ /api/get_open_repair_orders
@app.get("/api/get_open_repair_orders", summary="Get Open Repair Orders")
async def get_open_repair_orders():
    token = await get_access_token()
    if not token:
        return JSONResponse(content={"error": "Unable to authenticate"}, status_code=401)

    shop_id = 6212  # Replace with your real shop ID if needed
    status_ids = [2]  # Work In Progress
    url = (
        f"https://shop.tekmetric.com/api/v1/repair-orders"
        f"?shop={shop_id}&repairOrderStatusId={','.join(map(str, status_ids))}&size=50"
    )

    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers)
            logger.info(f"🛠️ Open ROs response status: {resp.status_code}")
            data = resp.json()

            if "content" not in data:
                logger.warning(f"⚠️ Unexpected response: {json.dumps(data, indent=2)}")
                return JSONResponse(content={"error": "Unexpected response format from Tekmetric"}, status_code=502)

            ros = data["content"]
            simplified = [
                {
                    "roNumber": ro.get("repairOrderNumber"),
                    "vehicle": (
                        f"{ro.get('vehicle', {}).get('year', 'Unknown')} "
                        f"{ro.get('vehicle', {}).get('make', '')} "
                        f"{ro.get('vehicle', {}).get('model', '')}"
                    ).strip(),
                    "customer": ro.get("customer", {}).get("fullName", "Unknown"),
                    "status": ro.get("repairOrderStatus", {}).get("name", "Unknown"),
                    "lastUpdated": ro.get("updatedDate")
                }
                for ro in ros
            ]
            logger.info(f"✅ Returning {len(simplified)} open ROs")
            return JSONResponse(content=simplified)

        except Exception as e:
            logger.exception("❌ Failed to fetch open repair orders")
            return JSONResponse(content={"error": str(e)}, status_code=500)

# ✅ /healthz
@app.get("/healthz", summary="Health Check")
async def healthz():
    return {"status": "ok"}

def get_customer(customer_id, base_url, access_token):
    url = f"{base_url}/api/v1/customers/{customer_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Customer fetch failed for ID {customer_id}: {response.status_code} - {response.text}")
        return {"firstName": "Unknown", "lastName": ""}

def get_vehicle(vehicle_id, base_url, access_token):
    url = f"{base_url}/api/v1/vehicles/{vehicle_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Vehicle fetch failed for ID {vehicle_id}: {response.status_code} - {response.text}")
        return {"year": "", "make": "Unknown", "model": ""}
