from fastmcp import FastMCP, Context
from dotenv import load_dotenv
from starlette.requests import Request
from starlette.responses import JSONResponse
import os
import httpx
import base64
import logging
import json

# Load environment variables from .env
load_dotenv()
logger = logging.getLogger("mcp-tekmetric")

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# Create the MCP tool server
mcp = FastMCP(
    name="Tekmetric API Tools",
    description="Tools for accessing real-time Tekmetric shop data via MCP.",
    streamable=True,
    transport="sse",
)

# Auth helper
async def get_access_token() -> str | None:
    if not CLIENT_ID or not CLIENT_SECRET:
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
            resp.raise_for_status()
            return resp.json().get("access_token")
        except Exception as e:
            logger.exception("Auth failed")
            return None

# MCP tool to get shops
@mcp.tool(name="get_shops", description="Get all shops available under this Tekmetric account")
async def get_shops(ctx: Context) -> str:
    token = await get_access_token()
    if not token:
        return json.dumps({"error": "Unable to authenticate"})

    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get("https://shop.tekmetric.com/api/v1/shops", headers=headers)
            resp.raise_for_status()
            return json.dumps(resp.json(), indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

# Health check route
@mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
async def healthz(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})

# MCP manifest route for ChatGPT
@mcp.custom_route("/mcp", methods=["GET"])
async def mcp_manifest(request: Request) -> JSONResponse:
    return JSONResponse({
        "servers": {
            "tekmetric": {
                "type": "sse",
                "url": "https://web-production-1dc1.up.railway.app/sse"
            }
        }
    })

# Entrypoint for uvicorn
asgi_app = mcp.sse_app
