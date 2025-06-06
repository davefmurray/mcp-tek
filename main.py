from fastmcp import FastMCP, Context
from dotenv import load_dotenv
from starlette.requests import Request
from starlette.responses import JSONResponse
import os
import httpx
import base64
import logging
import json

# Load .env
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-tekmetric")

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

mcp = FastMCP(
    name="Tekmetric API Tools",
    description="Live Tekmetric access via MCP tools.",
    streamable=True,
    transport="sse",
)

# Token fetcher
async def get_access_token() -> str | None:
    logger.info("🔐 Getting Tekmetric access token")
    logger.info(f"CLIENT_ID: {CLIENT_ID}")
    logger.info(f"CLIENT_SECRET: {CLIENT_SECRET}")

    if not CLIENT_ID or not CLIENT_SECRET:
        logger.error("❌ CLIENT_ID or CLIENT_SECRET missing")
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

@mcp.tool(name="get_shops", description="Get all shops linked to your Tekmetric account.")
async def get_shops(ctx: Context) -> str:
    logger.info("📡 get_shops tool called")
    token = await get_access_token()
    if not token:
        return json.dumps({"error": "Unable to authenticate"})

    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get("https://shop.tekmetric.com/api/v1/shops", headers=headers)
            logger.info(f"📦 Shops response status: {resp.status_code}")
            logger.info(f"📦 Shops response body: {await resp.aread()}")
            resp.raise_for_status()
            return json.dumps(resp.json(), indent=2)
        except Exception as e:
            logger.exception("❌ Failed to fetch shops")
            return json.dumps({"error": str(e)})

@mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
async def healthz(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})

@mcp.custom_route("/fake", methods=["GET"])
async def fake_get(request: Request) -> JSONResponse:
    return JSONResponse({"message": "Fake endpoint exists to satisfy GPT Builder validation."})

@mcp.custom_route("/mcp", methods=["GET"])
async def mcp_manifest(request: Request) -> JSONResponse:
    return JSONResponse({
        "openapi": "3.1.0",
        "info": {
            "title": "Tekmetric Tool Server",
            "version": "1.0.0"
        },
        "paths": {
            "/fake": {
                "get": {
                    "operationId": "fakeGet",
                    "summary": "Fake endpoint to make GPT Builder happy",
                    "responses": {
                        "200": {
                            "description": "Success"
                        }
                    }
                }
            }
        },
        "servers": [
            {
                "url": "https://web-production-1dc1.up.railway.app"
            }
        ]
    })

asgi_app = mcp.sse_app
