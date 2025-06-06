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

# Create FastMCP server
mcp = FastMCP(
    name="Tekmetric API Tools",
    description="Live Tekmetric access via MCP tools.",
    streamable=True,
    transport="sse",
)

# 🔐 Fetch Tekmetric token
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

# ✅ MCP Tool: get_shops
@mcp.tool(name="get_shops", description="Get all shops linked to your Tekmetric account.")
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

# ✅ Health check
@mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
async def healthz(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})

# ✅ Fake route required by GPT Builder test preview
@mcp.custom_route("/fake", methods=["GET"])
async def fake_get(request: Request) -> JSONResponse:
    return JSONResponse({"message": "Fake endpoint exists to satisfy GPT Builder validation."})

# ✅ OpenAPI 3.1.0 manifest for ChatGPT
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

# 🚀 Uvicorn entrypoint
asgi_app = mcp.sse_app
