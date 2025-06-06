from fastapi import APIRouter
import httpx
from main import get_access_token, TEKMETRIC_BASE_URL

router = APIRouter()

@router.get("/", summary="List Shops (Read-Only)")
async def list_shops():
    """
    Returns the list of shops accessible by this API token.
    Tekmetric endpoint: GET /api/v1/shops
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/shops", headers=headers)
        res.raise_for_status()
        return res.json()