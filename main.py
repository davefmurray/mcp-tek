import os
import time
import base64
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
import httpx

# Load environment variables
load_dotenv()

# Tekmetric configuration
TEKMETRIC_BASE_URL = "https://shop.tekmetric.com/api/v1"
CLIENT_ID         = os.getenv("CLIENT_ID")
CLIENT_SECRET     = os.getenv("CLIENT_SECRET")
SHOP_ID           = os.getenv("TEKMETRIC_SHOP_ID")

# FastAPI app
app = FastAPI()

# Cache for token
_token_cache = {"access_token": None, "expires_at": 0}

async def get_access_token() -> str:
    """
    Retrieves and caches OAuth2 token for Tekmetric.
    """
    global _token_cache
    # Return cached token if valid
    if _token_cache["access_token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["access_token"]

    # Request new token
    if not CLIENT_ID or not CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Missing CLIENT_ID or CLIENT_SECRET env vars")

    auth_header = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/json"
    }
    data = {"grant_type": "client_credentials"}

    async with httpx.AsyncClient() as client:
        res = await client.post(f"{TEKMETRIC_BASE_URL}/oauth/token", headers=headers, json=data)
        res.raise_for_status()
        token_data = res.json()

    access_token = token_data.get("access_token")
    expires_in   = token_data.get("expires_in", 0)

    if not access_token:
        raise HTTPException(status_code=500, detail="No access_token returned")

    _token_cache["access_token"] = access_token
    _token_cache["expires_at"]   = time.time() + expires_in - 10

    return access_token

@app.get("/api/debug/token", summary="Debug Token Retrieval")
async def debug_token():
    """
    Test endpoint to verify OAuth token retrieval.
    """
    token = await get_access_token()
    return {"token_length": len(token)}

@app.get("/api/health", summary="Health Check")
async def health_check():
    return {"status": "ok"}

# Include routers
from routers.shops import router as shops_router
from routers.customers import router as customers_router
from routers.vehicles import router as vehicles_router
from routers.employees import router as employees_router
from routers.appointments import router as appointments_router
from routers.repair_orders import router as repair_orders_router
from routers.jobs import router as jobs_router

app.include_router(shops_router, prefix="/api/shops", tags=["shops"])
app.include_router(customers_router, prefix="/api/customers", tags=["customers"])
app.include_router(vehicles_router, prefix="/api/vehicles", tags=["vehicles"])
app.include_router(employees_router, prefix="/api/employees", tags=["employees"])
app.include_router(appointments_router, prefix="/api/appointments", tags=["appointments"])
app.include_router(repair_orders_router, prefix="/api/repair_orders", tags=["repair_orders"])
app.include_router(jobs_router, prefix="/api/jobs", tags=["jobs"])
