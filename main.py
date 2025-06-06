import os
import time
import base64
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import httpx

# Load environment variables
load_dotenv()

# Tekmetric configuration
TEKMETRIC_BASE_URL = "https://shop.tekmetric.com/api/v1"
CLIENT_ID         = os.getenv("CLIENT_ID")
CLIENT_SECRET     = os.getenv("CLIENT_SECRET")
SHOP_ID           = os.getenv("TEKMETRIC_SHOP_ID")

# FastAPI app with OpenAPI config for ChatGPT
app = FastAPI(
    title="Tekmetric FastAPI for GPT Integration",
    version="1.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url=None,
    servers=[{"url": "https://web-production-1dc1.up.railway.app"}]
)

# Enable CORS so ChatGPT can fetch OpenAPI spec
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Cache for token
_token_cache = {"access_token": None, "expires_at": 0}

async def get_access_token() -> str:
    """
    Retrieves (and caches) an OAuth2 bearer token for Tekmetric,
    using form-encoded client credentials flow.
    """
    global _token_cache
    if _token_cache["access_token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["access_token"]

    if not CLIENT_ID or not CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Missing CLIENT_ID or CLIENT_SECRET")

    auth_header = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {"Authorization": f"Basic {auth_header}"}
    form = {"grant_type": "client_credentials"}

    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{TEKMETRIC_BASE_URL}/oauth/token",
            headers=headers,
            data=form
        )
        res.raise_for_status()
        token_data = res.json()

    access_token = token_data.get("access_token")
    expires_in   = token_data.get("expires_in", 0)
    if not access_token:
        raise HTTPException(status_code=500, detail="No access_token returned")

    _token_cache["access_token"] = access_token
    _token_cache["expires_at"]   = time.time() + expires_in - 10
    return access_token

@app.get("/api/health", summary="Health Check")
async def health_check():
    return {"status": "ok"}

@app.get("/api/debug/token", summary="Debug Token Retrieval")
async def debug_token():
    """
    Test endpoint to verify OAuth token retrieval.
    Returns token length or error message.
    """
    try:
        token = await get_access_token()
        return {"token_length": len(token)}
    except HTTPException:
        raise
    except Exception as e:
        return {"error": str(e)}

# Include all existing routers
from routers.shops import router as shops_router
from routers.shops_scope import router as shops_scope_router
from routers.customers import router as customers_router
from routers.vehicles import router as vehicles_router
from routers.employees import router as employees_router
from routers.appointments import router as appointments_router
from routers.repair_orders import router as repair_orders_router
from routers.jobs import router as jobs_router
from routers.canned_jobs import router as canned_jobs_router
from routers.inventory import router as inventory_router
from routers.inspections import router as inspections_router
from routers.job_clock import router as job_clock_router
from routers.labor import router as labor_router

app.include_router(shops_router, prefix="/api/shops", tags=["shops"])
app.include_router(shops_scope_router, prefix="/api/shops", tags=["shops_scope"])
app.include_router(customers_router, prefix="/api/customers", tags=["customers"])
app.include_router(vehicles_router, prefix="/api/vehicles", tags=["vehicles"])
app.include_router(employees_router, prefix="/api/employees", tags=["employees"])
app.include_router(appointments_router, prefix="/api/appointments", tags=["appointments"])
app.include_router(repair_orders_router, prefix="/api/repair_orders", tags=["repair_orders"])
app.include_router(jobs_router, prefix="/api/jobs", tags=["jobs"])
app.include_router(canned_jobs_router, prefix="/api/canned_jobs", tags=["canned_jobs"])
app.include_router(inventory_router, prefix="/api/inventory", tags=["inventory"])
app.include_router(inspections_router, prefix="/api/inspections", tags=["inspections"])
app.include_router(job_clock_router, prefix="/api/jobs", tags=["job_clock"])
app.include_router(labor_router, prefix="/api/labor", tags=["labor"])
