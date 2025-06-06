from fastapi import APIRouter, HTTPException
import httpx
from main import get_access_token, TEKMETRIC_BASE_URL

router = APIRouter()

@router.get("/{shop_id}", summary="Get Shop Details")
async def get_shop(shop_id: int):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/shops/{shop_id}", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Shop ID {shop_id} not found")
        res.raise_for_status()
        return res.json()

@router.delete("/{shop_id}/scope", summary="Remove Shop Scope")
async def remove_shop_scope(shop_id: int):
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        res = await client.delete(f"{TEKMETRIC_BASE_URL}/shops/{shop_id}/scope", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Shop ID {shop_id} not found or scope not applied")
        res.raise_for_status()
        return {"detail": f"Scope removed for Shop ID {shop_id}"}