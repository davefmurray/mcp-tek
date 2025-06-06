from fastapi import FastAPI
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import os
import httpx
import base64
import json
import logging

# Load .env vars
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tekmetric")

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# ✅ Main FastAPI app with OpenAPI servers block for GPT Builder
app = FastAPI(
    title="Tekmetric API",
    version="1.0.0",
    servers=[
        {"url": "https://web-production-1dc1.up.railway.app"}
    ]
)

# 🔐 Get Tekmetric access token
async def get_access_token() -> str | None:
    logger.info("🔐 Getting Tekmetric access token")
    if not CLIENT_ID or not CLIENT_SECRET:
        logger.error("Missing CLIENT_ID or CLIENT_SECRET")
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
            logger.info(f"🔑 Token response body: {await resp.aread()}")
            resp.raise_for_status()
            return resp.json().get("access_token")
        except Exception as e:
            logger.exception("❌ Failed to fetch access token")
            return None

# ✅ REST endpoint for GPT to hit
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
            data = await resp.json()
            return JSONResponse(content=data)
        except Exception as e:
            logger.exception("❌ Failed to fetch shops")
            return JSONResponse(content={"error": str(e)}, status_code=500)

# ✅ Health check
@app.get("/healthz", summary="Health Check")
async def healthz():
    return {"status": "ok"}
