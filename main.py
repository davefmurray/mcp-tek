from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import os
import httpx
import base64
import json
import logging

# Setup
load_dotenv()
app = FastAPI()
logger = logging.getLogger("tekmetric")
logging.basicConfig(level=logging.INFO)

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

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
            logger.info(f"Token response status: {resp.status_code}")
            logger.info(f"Token body: {await resp.aread()}")
            resp.raise_for_status()
            return resp.json().get("access_token")
        except Exception as e:
            logger.exception("❌ Failed to fetch access token")
            return None

@app.get("/api/get_shops")
async def get_shops():
    token = await get_access_token()
    if not token:
        return JSONResponse(content={"error": "Unable to authenticate"}, status_code=401)

    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get("https://shop.tekmetric.com/api/v1/shops", headers=headers)
            logger.info(f"Shops response status: {resp.status_code}")
            data = await resp.json()
            return JSONResponse(content=data)
        except Exception as e:
            logger.exception("❌ Failed to fetch shops")
            return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
