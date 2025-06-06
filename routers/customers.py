from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel, Field
import httpx
from main import get_access_token, TEKMETRIC_BASE_URL, SHOP_ID

router = APIRouter()

class CustomerCreate(BaseModel):
    """
    Fields required to create a new Customer.
    Tekmetric endpoint: POST /api/v1/customers
    """
    firstName: str = Field(..., description="Customer first name")
    lastName: str = Field(..., description="Customer last name")
    email: List[str] = Field(..., description="Array of email addresses")
    phones: List[dict] = Field(..., description="Array of phone objects")
    address: dict = Field(..., description="Address JSON {address1, city, state, zip, ...}")
    okForMarketing: Optional[bool] = Field(False, description="Is customer OK for marketing")
    notes: Optional[str] = Field(None, description="Any notes")
    customerTypeId: Optional[int] = Field(1, description="1=PERSON (default), 2=BUSINESS")

class CustomerUpdate(BaseModel):
    """
    Fields allowed to update an existing Customer.
    Tekmetric endpoint: PATCH /api/v1/customers/{id}
    """
    firstName: Optional[str] = Field(None, description="Customer first name")
    lastName: Optional[str] = Field(None, description="Customer last name")
    email: Optional[List[str]] = Field(None, description="Array of email addresses")
    phones: Optional[List[dict]] = Field(None, description="Array of phone objects")
    address: Optional[dict] = Field(None, description="Address JSON {address1, city, state, zip, ...}")
    okForMarketing: Optional[bool] = Field(None, description="Is customer OK for marketing")
    notes: Optional[str] = Field(None, description="Any notes")
    customerTypeId: Optional[int] = Field(None, description="CustomerType (1=PERSON, 2=BUSINESS)")

@router.get("/", summary="Search Customers")
async def search_customers(search: str = Query(..., description="Search term (substring)")):
    """
    Returns up to 10 matching Customers by substring search.
    Tekmetric endpoint: GET /api/v1/customers
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params = {"shop": SHOP_ID, "search": search, "size": 10}

    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/customers", headers=headers, params=params)
        res.raise_for_status()
        return {"customers": res.json().get("content", [])}

@router.get("/{customer_id}", summary="Get Customer by ID")
async def get_customer_by_id(customer_id: int):
    """
    Get a single Customer by ID.
    Tekmetric endpoint: GET /api/v1/customers/{id}
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/customers/{customer_id}", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Customer ID {customer_id} not found")
        res.raise_for_status()
        return res.json()

@router.post("/", summary="Create Customer")
async def create_customer(customer: CustomerCreate):
    """
    Create a new Customer in Tekmetric.
    Tekmetric endpoint: POST /api/v1/customers
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = customer.dict()
    payload["shopId"] = SHOP_ID

    async with httpx.AsyncClient() as client:
        res = await client.post(f"{TEKMETRIC_BASE_URL}/customers", headers=headers, json=payload)
        res.raise_for_status()
        return res.json()

@router.patch("/{customer_id}", summary="Update Customer")
async def update_customer(customer_id: int, customer: CustomerUpdate):
    """
    Update fields on an existing Customer.
    Tekmetric endpoint: PATCH /api/v1/customers/{id}
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = customer.dict(exclude_unset=True)

    async with httpx.AsyncClient() as client:
        # Check if customer exists
        check = await client.get(f"{TEKMETRIC_BASE_URL}/customers/{customer_id}", headers=headers)
        if check.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Customer ID {customer_id} not found")

        payload["shopId"] = SHOP_ID
        res = await client.patch(f"{TEKMETRIC_BASE_URL}/customers/{customer_id}", headers=headers, json=payload)
        res.raise_for_status()
        return res.json()

@router.delete("/{customer_id}", summary="Delete Customer")
async def delete_customer(customer_id: int):
    """
    Deletes (archives) a Customer.
    Tekmetric endpoint: DELETE /api/v1/customers/{id}
    """
    token = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        res = await client.delete(f"{TEKMETRIC_BASE_URL}/customers/{customer_id}", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Customer ID {customer_id} not found")
        res.raise_for_status()
        return {"detail": f"Customer {customer_id} deleted"}