import os
import time
import base64
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query, Body
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import httpx

load_dotenv()

# ───────────────────────────────────────────────────────────
# Environment & Constants
# ───────────────────────────────────────────────────────────
TEKMETRIC_BASE_URL = "https://shop.tekmetric.com/api/v1"
CLIENT_ID         = os.getenv("CLIENT_ID")
CLIENT_SECRET     = os.getenv("CLIENT_SECRET")
SHOP_ID           = os.getenv("TEKMETRIC_SHOP_ID")

# ───────────────────────────────────────────────────────────
# FastAPI App
# ───────────────────────────────────────────────────────────
app = FastAPI()

# ───────────────────────────────────────────────────────────
# Helper: OAuth2 Token Retrieval (Client Credentials)
# ───────────────────────────────────────────────────────────
_token_cache = {"access_token": None, "expires_at": 0}

async def get_access_token() -> str:
    """
    Retrieves (and caches) an OAuth2 bearer token for Tekmetric.
    """
    global _token_cache

    # If we already have a token that hasn't expired, return it
    if _token_cache["access_token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["access_token"]

    # Otherwise, request a new one
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

    # Cache it slightly shorter than its lifetime
    _token_cache["access_token"] = access_token
    _token_cache["expires_at"]   = time.time() + expires_in - 10

    return access_token

# ───────────────────────────────────────────────────────────
# 1. Health Check
# ───────────────────────────────────────────────────────────
@app.get("/api/health", summary="Health Check")
async def health_check():
    return {"status": "ok"}

# ───────────────────────────────────────────────────────────
# Routers
# ───────────────────────────────────────────────────────────

# --- Shops Router ---
from routers.shops import router as shops_router
app.include_router(shops_router, prefix="/api/shops", tags=["shops"])

# --- Customers Router ---
from routers.customers import router as customers_router
app.include_router(customers_router, prefix="/api/customers", tags=["customers"])

# --- Vehicles Router ---
from routers.vehicles import router as vehicles_router
app.include_router(vehicles_router, prefix="/api/vehicles", tags=["vehicles"])

# --- Employees Router ---
from routers.employees import router as employees_router
app.include_router(employees_router, prefix="/api/employees", tags=["employees"])

# --- Appointments Router ---
from routers.appointments import router as appointments_router
app.include_router(appointments_router, prefix="/api/appointments", tags=["appointments"])

# --- Repair Orders Router ---
from routers.repair_orders import router as repair_orders_router
app.include_router(repair_orders_router, prefix="/api/repair_orders", tags=["repair_orders"])

# --- Jobs Router ---
from routers.jobs import router as jobs_router
app.include_router(jobs_router, prefix="/api/jobs", tags=["jobs"])
