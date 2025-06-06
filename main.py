import os
import asyncio
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
CLIENT_ID        = os.getenv("CLIENT_ID")
CLIENT_SECRET    = os.getenv("CLIENT_SECRET")
SHOP_ID          = int(os.getenv("TEKMETRIC_SHOP_ID", 0))

if not CLIENT_ID or not CLIENT_SECRET:
    raise RuntimeError("CLIENT_ID or CLIENT_SECRET not set")
if not SHOP_ID:
    raise RuntimeError("TEKMETRIC_SHOP_ID not set")

app = FastAPI(
    title="JJ Auto API",
    description="FastAPI-based AI Assistant for Tekmetric integration",
    version="1.0.0",
    servers=[{"url": "https://web-production-1dc1.up.railway.app"}]
)


# ───────────────────────────────────────────────────────────
# Utility: Acquire OAuth2 Access Token
# ───────────────────────────────────────────────────────────
async def get_access_token() -> str:
    auth_header = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"grant_type": "client_credentials"}
    async with httpx.AsyncClient() as client:
        res = await client.post(f"{TEKMETRIC_BASE_URL}/oauth/token", headers=headers, data=data)
        res.raise_for_status()
        return res.json()["access_token"]


# ───────────────────────────────────────────────────────────
# 1. Health Check
# ───────────────────────────────────────────────────────────
@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


# ───────────────────────────────────────────────────────────
# 2. Shops (READ-ONLY)
# ───────────────────────────────────────────────────────────
@app.get("/api/get_shops")
async def get_shops():
    """
    Returns the list of shops accessible by this API token.
    Tekmetric endpoint: GET /api/v1/shops :contentReference[oaicite:31]{index=31}
    """
    token   = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/shops", headers=headers)
        res.raise_for_status()
        return res.json()


# ───────────────────────────────────────────────────────────
# 3. Repair Orders
# ───────────────────────────────────────────────────────────

class RepairOrderCreate(BaseModel):
    """
    Fields required to create a Repair Order:
    - customerId: integer (required)
    - vehicleId:  integer (required)
    - technicianId: Optional[int]
    - serviceWriterId: Optional[int]
    - appointmentStartTime: Optional[str]  (ISO-8601)
    - notes: Optional[str]
    Additional fields may be added (e.g., keytag, milesIn/milesOut) as needed.
    Based on Tekmetric API spec: POST /api/v1/repair-orders :contentReference[oaicite:32]{index=32}
    """
    customerId: int = Field(..., description="Existing Tekmetric Customer ID")
    vehicleId:  int = Field(..., description="Existing Tekmetric Vehicle ID")
    technicianId: Optional[int] = Field(None, description="Employee ID assigned to technician")
    serviceWriterId: Optional[int] = Field(None, description="Employee ID assigned as service writer")
    appointmentStartTime: Optional[str] = Field(
        None, description="ISO-8601 timestamp for appointment start"
    )
    notes: Optional[str] = Field(None, description="Any notes on the repair order")


class RepairOrderUpdate(BaseModel):
    """
    Fields allowed when updating a Repair Order.
    Based on Tekmetric API spec: PATCH /api/v1/repair-orders/{id} :contentReference[oaicite:33]{index=33}
    """
    keyTag:          Optional[str] = Field(None, description="KeyTag label")
    milesIn:         Optional[int] = Field(None, description="Mileage in on RO")
    milesOut:        Optional[int] = Field(None, description="Mileage out on RO")
    technicianId:    Optional[int] = Field(None, description="Assign technician by employee ID")
    serviceWriterId: Optional[int] = Field(None, description="Assign service writer by employee ID")
    customerTimeOut: Optional[str] = Field(None, description="Promise time (ISO-8601)")


@app.get("/api/get_open_repair_orders")
async def get_open_repair_orders():
    """
    Returns all Repair Orders in status 'Estimate' or 'Work-in-Progress' for this shop.
    Tekmetric endpoint: GET /api/v1/repair-orders?shop={shop}&repairOrderStatusId=[1,2] :contentReference[oaicite:34]{index=34}
    """
    token   = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params  = {
        "shop": SHOP_ID,
        "repairOrderStatusId": [1, 2],  # 1=Estimate, 2=Work-in-Progress
        "size": 100
    }

    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/repair-orders", headers=headers, params=params)
        res.raise_for_status()
        ros = res.json().get("content", [])

        async def hydrate(ro: dict):
            # Fetch vehicle details
            vehicle_str = "Unknown"
            if ro.get("vehicleId"):
                try:
                    v_res = await client.get(
                        f"{TEKMETRIC_BASE_URL}/vehicles/{ro['vehicleId']}", headers=headers
                    )
                    v_res.raise_for_status()
                    v = v_res.json()
                    vehicle_str = f"{v.get('year','')} {v.get('make','')} {v.get('model','')}".strip()
                except:
                    pass

            # Fetch customer details
            customer_str = "Unknown"
            if ro.get("customerId"):
                try:
                    c_res = await client.get(
                        f"{TEKMETRIC_BASE_URL}/customers/{ro['customerId']}", headers=headers
                    )
                    c_res.raise_for_status()
                    c = c_res.json()
                    customer_str = f"{c.get('firstName','')} {c.get('lastName','')}".strip()
                except:
                    pass

            return {
                "id": ro.get("id"),
                "roNumber": ro.get("repairOrderNumber"),
                "vehicle": vehicle_str or "Unknown",
                "customer": customer_str or "Unknown",
                "status": ro.get("repairOrderStatus", {}).get("name", "Unknown"),
                "lastUpdated": ro.get("updatedDate")
            }

        return await asyncio.gather(*(hydrate(ro) for ro in ros))


@app.get("/api/get_repair_order/{ro_id}")
async def get_repair_order(ro_id: int):
    """
    Fetches a single Repair Order by its internal ID.
    Tekmetric endpoint: GET /api/v1/repair-orders/{id} :contentReference[oaicite:35]{index=35}
    """
    token   = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/repair-orders/{ro_id}", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"RO ID {ro_id} not found")
        res.raise_for_status()
        return res.json()


@app.post("/api/create_repair_order")
async def create_repair_order(payload: RepairOrderCreate):
    """
    Creates a new Repair Order in Tekmetric.
    Tekmetric endpoint: POST /api/v1/repair-orders :contentReference[oaicite:36]{index=36}
    """
    token   = await get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = payload.dict()
    data["shopId"] = SHOP_ID

    async with httpx.AsyncClient() as client:
        res = await client.post(f"{TEKMETRIC_BASE_URL}/repair-orders", headers=headers, json=data)
        if res.status_code >= 400:
            raise HTTPException(status_code=res.status_code, detail=res.text)
        return res.json()


@app.patch("/api/update_repair_order/{ro_id}")
async def update_repair_order(ro_id: int, payload: RepairOrderUpdate):
    """
    Updates fields on an existing Repair Order.
    Tekmetric endpoint: PATCH /api/v1/repair-orders/{id} :contentReference[oaicite:37]{index=37}
    """
    token   = await get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = payload.dict(exclude_unset=True)

    async with httpx.AsyncClient() as client:
        # Check existence first
        check = await client.get(f"{TEKMETRIC_BASE_URL}/repair-orders/{ro_id}", headers=headers)
        if check.status_code == 404:
            raise HTTPException(status_code=404, detail=f"RO ID {ro_id} not found")
        res = await client.patch(f"{TEKMETRIC_BASE_URL}/repair-orders/{ro_id}", headers=headers, json=data)
        res.raise_for_status()
        return res.json()


@app.delete("/api/delete_repair_order/{ro_id}")
async def delete_repair_order(ro_id: int):
    """
    Deletes (voids) a Repair Order.
    Tekmetric endpoint: DELETE /api/v1/repair-orders/{id} :contentReference[oaicite:38]{index=38}
    """
    token   = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        res = await client.delete(f"{TEKMETRIC_BASE_URL}/repair-orders/{ro_id}", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"RO ID {ro_id} not found")
        res.raise_for_status()
        return {"detail": f"Repair Order {ro_id} deleted"}


# ───────────────────────────────────────────────────────────
# 4. Jobs
# ───────────────────────────────────────────────────────────

class JobCreate(BaseModel):
    """
    Fields to create a new Job under an existing Repair Order.
    Tekmetric endpoint: POST /api/v1/jobs :contentReference[oaicite:39]{index=39}
    """
    repairOrderId: int = Field(..., description="Internal Repair Order ID")
    vehicleId:     int = Field(..., description="Vehicle ID (must match RO vehicle)")
    customerId:    int = Field(..., description="Customer ID (must match RO customer)")
    name:          str = Field(..., description="Job name or description")
    jobCategoryName: Optional[str] = Field(None, description="Category (optional)")
    technicianId:  Optional[int] = Field(None, description="Employee ID for tech")
    note:          Optional[str] = Field(None, description="Any job-specific notes")


class JobUpdate(BaseModel):
    """
    Fields to update an existing Job.
    Tekmetric endpoint: PATCH /api/v1/jobs/{id} :contentReference[oaicite:40]{index=40}
    """
    name:            Optional[str] = Field(None, description="Updated job name")
    authorized:      Optional[bool] = Field(None, description="Authorized by customer")
    technicianId:    Optional[int] = Field(None, description="Re-assign technician by ID")
    note:            Optional[str] = Field(None, description="Update job note")
    partsTotal:      Optional[int] = Field(None, description="Parts total in cents")
    laborTotal:      Optional[int] = Field(None, description="Labor total in cents")
    archived:        Optional[bool] = Field(None, description="Archive (decline) job")


@app.get("/api/get_jobs_by_ro")
async def get_jobs_by_ro(ro_id: int):
    """
    List all Jobs for a given Repair Order.
    Tekmetric endpoint: GET /api/v1/jobs?repairOrderId={id}&shop={shop} :contentReference[oaicite:41]{index=41}
    """
    token   = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params  = {"shop": SHOP_ID, "repairOrderId": ro_id, "size": 100}

    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/jobs", headers=headers, params=params)
        res.raise_for_status()
        jobs = res.json().get("content", [])
        output = []
        for job in jobs:
            tech_name = "Unassigned"
            if job.get("technicianId"):
                try:
                    tech_res = await client.get(
                        f"{TEKMETRIC_BASE_URL}/employees/{job['technicianId']}",
                        headers=headers
                    )
                    tech_res.raise_for_status()
                    tech = tech_res.json()
                    tech_name = f"{tech.get('firstName','')} {tech.get('lastName','')}".strip()
                except:
                    pass

            output.append({
                "jobId": job.get("id"),
                "jobName": job.get("name"),
                "tech": tech_name,
                "note": job.get("note"),
                "authorized": job.get("authorized"),
                "laborTotal": job.get("laborTotal"),
                "partsTotal": job.get("partsTotal"),
                "status": "Archived" if job.get("archived") else "Active",
                "createdDate": job.get("createdDate"),
                "updatedDate": job.get("updatedDate")
            })
        return {"repairOrderId": ro_id, "jobCount": len(output), "jobs": output}


@app.post("/api/create_job")
async def create_job(payload: JobCreate):
    """
    Creates a new Job under the specified Repair Order.
    Tekmetric endpoint: POST /api/v1/jobs :contentReference[oaicite:42]{index=42}
    """
    token   = await get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = payload.dict()
    data["shop"] = SHOP_ID

    async with httpx.AsyncClient() as client:
        # Validate RO exists first
        ro_check = await client.get(f"{TEKMETRIC_BASE_URL}/repair-orders/{payload.repairOrderId}", headers=headers)
        if ro_check.status_code == 404:
            raise HTTPException(status_code=404, detail=f"RO ID {payload.repairOrderId} not found")

        res = await client.post(f"{TEKMETRIC_BASE_URL}/jobs", headers=headers, json=data)
        if res.status_code >= 400:
            raise HTTPException(status_code=res.status_code, detail=res.text)
        return res.json()


@app.patch("/api/update_job/{job_id}")
async def update_job(job_id: int, payload: JobUpdate):
    """
    Updates an existing Job.
    Tekmetric endpoint: PATCH /api/v1/jobs/{id} :contentReference[oaicite:43]{index=43}
    """
    token   = await get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = payload.dict(exclude_unset=True)

    async with httpx.AsyncClient() as client:
        # Check job exists first
        check = await client.get(f"{TEKMETRIC_BASE_URL}/jobs/{job_id}", headers=headers)
        if check.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Job ID {job_id} not found")

        res = await client.patch(f"{TEKMETRIC_BASE_URL}/jobs/{job_id}", headers=headers, json=data)
        res.raise_for_status()
        return res.json()


@app.delete("/api/delete_job/{job_id}")
async def delete_job(job_id: int):
    """
    Deletes (archives) a Job.
    Tekmetric endpoint: DELETE /api/v1/jobs/{id} :contentReference[oaicite:44]{index=44}
    """
    token   = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        # Deletion in Tekmetric is effectively archiving the job
        res = await client.delete(f"{TEKMETRIC_BASE_URL}/jobs/{job_id}", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Job ID {job_id} not found")
        res.raise_for_status()
        return {"detail": f"Job {job_id} deleted"}


# ───────────────────────────────────────────────────────────
# 5. Customers
# ───────────────────────────────────────────────────────────

class CustomerCreate(BaseModel):
    """
    Fields required to create a new Customer.
    Tekmetric endpoint: POST /api/v1/customers :contentReference[oaicite:45]{index=45}
    """
    firstName:   str                   = Field(..., description="Customer first name")
    lastName:    str                   = Field(..., description="Customer last name")
    email:       List[str]             = Field(..., description="Array of email addresses")
    phones:      List[dict]            = Field(..., description="Array of phone objects")
    address:     dict                  = Field(..., description="Address JSON {address1, city, state, zip, ...}")
    okForMarketing: Optional[bool]     = Field(False, description="Is customer OK for marketing")
    notes:       Optional[str]         = Field(None, description="Any notes")
    customerTypeId: Optional[int]      = Field(1, description="1=PERSON (default), 2=BUSINESS")


class CustomerUpdate(BaseModel):
    """
    Fields allowed to update an existing Customer.
    Tekmetric endpoint: PATCH /api/v1/customers/{id} :contentReference[oaicite:46]{index=46}
    """
    firstName:       Optional[str]      = Field(None, description="Customer first name")
    lastName:        Optional[str]      = Field(None, description="Customer last name")
    email:           Optional[List[str]] = Field(None, description="Array of email addresses")
    phones:          Optional[List[dict]] = Field(None, description="Array of phone JSON objects")
    address:         Optional[dict]     = Field(None, description="Address JSON")
    okForMarketing:  Optional[bool]     = Field(None, description="Is customer OK for marketing")
    notes:           Optional[str]      = Field(None, description="Any notes")
    customerTypeId:  Optional[int]      = Field(None, description="CustomerType (1=PERSON, 2=BUSINESS)")


@app.get("/api/get_customer")
async def get_customer(search: str):
    """
    Returns up to 10 matching Customers by substring search.
    Tekmetric endpoint: GET /api/v1/customers?shop={shop}&search={search}&size=10 :contentReference[oaicite:47]{index=47}
    """
    token   = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params  = {"shop": SHOP_ID, "search": search, "size": 10}

    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/customers", headers=headers, params=params)
        res.raise_for_status()
        customers = res.json().get("content", [])
        results = []
        for c in customers:
            phone_list = c.get("phone", [])
            phone_str  = phone_list[0]["number"] if phone_list else "N/A"
            results.append({
                "id": c.get("id"),
                "name": f"{c.get('firstName','')} {c.get('lastName','')}".strip(),
                "email": c.get("email", "N/A"),
                "phone": phone_str,
                "okForMarketing": c.get("okForMarketing"),
                "notes": c.get("notes"),
                "address": c.get("address", {}).get("fullAddress", "N/A"),
                "created": c.get("createdDate"),
                "updated": c.get("updatedDate")
            })
        return {"query": search, "matchCount": len(results), "results": results}


@app.get("/api/get_customer_by_id")
async def get_customer_by_id(id: int):
    """
    Fetches a single customer by ID (paging through if needed).
    Tekmetric endpoint: GET /api/v1/customers?shop={shop}&page={n}&size=100 :contentReference[oaicite:48]{index=48}
    """
    token   = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        page = 0
        while True:
            params = {"shop": SHOP_ID, "size": 100, "page": page}
            res    = await client.get(f"{TEKMETRIC_BASE_URL}/customers", headers=headers, params=params)
            res.raise_for_status()
            customers = res.json().get("content", [])
            if not customers:
                break
            for c in customers:
                if c.get("id") == id:
                    phone_list = c.get("phone", [])
                    phone_str  = phone_list[0]["number"] if phone_list else "N/A"
                    return {
                        "id": c.get("id"),
                        "name": f"{c.get('firstName','')} {c.get('lastName','')}".strip(),
                        "email": c.get("email", "N/A"),
                        "phone": phone_str,
                        "okForMarketing": c.get("okForMarketing"),
                        "notes": c.get("notes"),
                        "address": c.get("address", {}).get("fullAddress", "N/A"),
                        "customerType": c.get("customerType", {}).get("name"),
                        "created": c.get("createdDate"),
                        "updated": c.get("updatedDate")
                    }
            page += 1

    raise HTTPException(status_code=404, detail=f"Customer ID {id} not found")


@app.get("/api/get_full_customer_history")
async def get_full_customer_history(id: int):
    """
    Returns the full service history for a customer:
      • customer profile
      • all vehicles for that customer
      • for each vehicle, all ROs
      • for each RO, all jobs
    Combines: GET /customers/{id}, /vehicles?customerId={id}, /repair-orders?vehicleId={vid}, /jobs?repairOrderId={roid} 
    """
    token   = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        # 1) fetch customer by ID
        c_res = await client.get(f"{TEKMETRIC_BASE_URL}/customers/{id}", headers=headers)
        if c_res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Customer ID {id} not found")
        c_res.raise_for_status()
        customer = c_res.json()

        # 2) fetch all vehicles for this customer
        v_params = {"shop": SHOP_ID, "customerId": id, "size": 100}
        v_res    = await client.get(f"{TEKMETRIC_BASE_URL}/vehicles", headers=headers, params=v_params)
        v_res.raise_for_status()
        vehicles = v_res.json().get("content", [])

        async def get_ros_and_jobs(vehicle: dict):
            # 3) fetch all ROs for this vehicle
            ro_params = {"shop": SHOP_ID, "vehicleId": vehicle["id"], "size": 100}
            ro_res    = await client.get(f"{TEKMETRIC_BASE_URL}/repair-orders", headers=headers, params=ro_params)
            ro_res.raise_for_status()
            ros = ro_res.json().get("content", [])

            async def get_jobs_for_ro(ro: dict):
                job_params = {"shop": SHOP_ID, "repairOrderId": ro["id"], "size": 100}
                job_res    = await client.get(f"{TEKMETRIC_BASE_URL}/jobs", headers=headers, params=job_params)
                job_res.raise_for_status()
                jobs = job_res.json().get("content", [])
                return {
                    "roNumber": ro.get("repairOrderNumber"),
                    "status": ro.get("repairOrderStatus", {}).get("name"),
                    "jobs": [
                        {"jobName": j.get("name"), "techId": j.get("technicianId")}
                        for j in jobs
                    ]
                }

            ro_jobs = await asyncio.gather(*(get_jobs_for_ro(ro) for ro in ros))
            return {
                "vehicleId": vehicle["id"],
                "year": vehicle.get("year"),
                "make": vehicle.get("make"),
                "model": vehicle.get("model"),
                "repairOrders": ro_jobs
            }

        vehicles_with_hist = await asyncio.gather(*(get_ros_and_jobs(v) for v in vehicles))

        phone_list = customer.get("phone", [])
        phone_str  = phone_list[0]["number"] if phone_list else "N/A"
        return {
            "customer": {
                "id": customer.get("id"),
                "name": f"{customer.get('firstName','')} {customer.get('lastName','')}".strip(),
                "email": customer.get("email", "N/A"),
                "phone": phone_str,
                "address": customer.get("address", {}).get("fullAddress", "N/A")
            },
            "vehicles": vehicles_with_hist
        }


@app.post("/api/create_customer")
async def create_customer(payload: CustomerCreate):
    """
    Creates a new Customer.
    Tekmetric endpoint: POST /api/v1/customers :contentReference[oaicite:49]{index=49}
    """
    token   = await get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = payload.dict()
    data["shopId"] = SHOP_ID

    async with httpx.AsyncClient() as client:
        res = await client.post(f"{TEKMETRIC_BASE_URL}/customers", headers=headers, json=data)
        if res.status_code >= 400:
            raise HTTPException(status_code=res.status_code, detail=res.text)
        return res.json()


@app.patch("/api/update_customer/{customer_id}")
async def update_customer(customer_id: int, payload: CustomerUpdate):
    """
    Updates fields on an existing Customer.
    Tekmetric endpoint: PATCH /api/v1/customers/{id} :contentReference[oaicite:50]{index=50}
    """
    token   = await get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = payload.dict(exclude_unset=True)

    async with httpx.AsyncClient() as client:
        # Check if customer exists
        check = await client.get(f"{TEKMETRIC_BASE_URL}/customers/{customer_id}", headers=headers)
        if check.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Customer ID {customer_id} not found")

        res = await client.patch(f"{TEKMETRIC_BASE_URL}/customers/{customer_id}", headers=headers, json=data)
        res.raise_for_status()
        return res.json()


@app.delete("/api/delete_customer/{customer_id}")
async def delete_customer(customer_id: int):
    """
    Deletes (archives) a Customer.
    Tekmetric endpoint: DELETE /api/v1/customers/{id} :contentReference[oaicite:51]{index=51}
    """
    token   = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        res = await client.delete(f"{TEKMETRIC_BASE_URL}/customers/{customer_id}", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Customer ID {customer_id} not found")
        res.raise_for_status()
        return {"detail": f"Customer {customer_id} deleted"}


# ───────────────────────────────────────────────────────────
# 6. Vehicles
# ───────────────────────────────────────────────────────────

class VehicleCreate(BaseModel):
    """
    Fields required to create a new Vehicle.
    Tekmetric endpoint: POST /api/v1/vehicles :contentReference[oaicite:52]{index=52}
    """
    customerId:    int    = Field(..., description="Existing Customer ID for this vehicle")
    year:         int    = Field(..., description="Year of the vehicle")
    make:         str    = Field(..., description="Make (e.g., 'Ford')")
    model:        str    = Field(..., description="Model (e.g., 'Escape')")
    subModel:    Optional[str] = Field(None, description="Submodel (optional)")
    engine:      Optional[str] = Field(None, description="Engine spec (optional)")
    color:       Optional[str] = Field(None, description="Color (optional)")
    licensePlate: Optional[str] = Field(None, description="License plate (optional)")
    state:       Optional[str] = Field(None, description="State of registration (optional)")
    vin:          Optional[str] = Field(None, description="Vehicle VIN (optional)")
    driveType:    Optional[str] = Field(None, description="e.g., 'AWD'")
    transmission: Optional[str] = Field(None, description="e.g., 'Automatic'")
    bodyType:     Optional[str] = Field(None, description="Body (e.g., 'SUV')")
    notes:       Optional[str] = Field(None, description="Any notes")
    unitNumber:   Optional[str] = Field(None, description="Unit number (optional)")


class VehicleUpdate(BaseModel):
    """
    Fields allowed to update an existing Vehicle.
    Tekmetric endpoint: PATCH /api/v1/vehicles/{id} :contentReference[oaicite:53]{index=53}
    """
    year:         Optional[int]   = Field(None, description="Year of the vehicle")
    make:         Optional[str]   = Field(None, description="Make")
    model:        Optional[str]   = Field(None, description="Model")
    subModel:    Optional[str]   = Field(None, description="Submodel")
    engine:      Optional[str]   = Field(None, description="Engine details")
    color:       Optional[str]   = Field(None, description="Color")
    licensePlate: Optional[str]   = Field(None, description="License plate")
    state:       Optional[str]   = Field(None, description="Plate state")
    vin:          Optional[str]   = Field(None, description="VIN")
    driveType:    Optional[str]   = Field(None, description="Drive type")
    transmission: Optional[str]   = Field(None, description="Transmission")
    bodyType:     Optional[str]   = Field(None, description="Body type")
    notes:       Optional[str]   = Field(None, description="Any notes")
    unitNumber:   Optional[str]   = Field(None, description="Unit number")


@app.get("/api/get_vehicles_by_customer")
async def get_vehicles_by_customer(customer_id: int):
    """
    Returns all vehicles for a given customer.
    Tekmetric endpoint: GET /api/v1/vehicles?shop={shop}&customerId={id}&size=100 :contentReference[oaicite:54]{index=54}
    """
    token   = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params  = {"shop": SHOP_ID, "customerId": customer_id, "size": 100}

    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/vehicles", headers=headers, params=params)
        res.raise_for_status()
        vehicles = res.json().get("content", [])
        simplified = []
        for v in vehicles:
            simplified.append({
                "vehicleId": v.get("id"),
                "year": v.get("year"),
                "make": v.get("make"),
                "model": v.get("model"),
                "vin": v.get("vin", "N/A"),
                "licensePlate": v.get("licensePlate", "N/A")
            })
        return simplified


@app.get("/api/get_vehicle")
async def get_vehicle(vehicle_id: int):
    """
    Returns a single Vehicle by ID.
    Tekmetric endpoint: GET /api/v1/vehicles/{id} :contentReference[oaicite:55]{index=55}
    """
    token   = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/vehicles/{vehicle_id}", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Vehicle ID {vehicle_id} not found")
        res.raise_for_status()
        return res.json()


@app.get("/api/get_service_by_vehicle")
async def get_service_by_vehicle(
    vehicle_id: int,
    year: Optional[int] = Query(None, description="Filter ROs by creation year (YYYY)")
):
    """
    Lists all Repair Orders on a given vehicle. Optionally filter by year.
    Tekmetric endpoint: GET /api/v1/repair-orders?shop={shop}&vehicleId={id}&size=100 :contentReference[oaicite:56]{index=56}
    """
    token   = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    params  = {"shop": SHOP_ID, "vehicleId": vehicle_id, "size": 100}

    async with httpx.AsyncClient() as client:
        res = await client.get(f"{TEKMETRIC_BASE_URL}/repair-orders", headers=headers, params=params)
        res.raise_for_status()
        ros = res.json().get("content", [])
        filtered = []
        for ro in ros:
            created = ro.get("createdDate", "")
            if year and not created.startswith(str(year)):
                continue
            filtered.append({
                "roNumber": ro.get("repairOrderNumber"),
                "status": ro.get("repairOrderStatus", {}).get("name", "Unknown"),
                "createdDate": created
            })
        return filtered


@app.post("/api/create_vehicle")
async def create_vehicle(payload: VehicleCreate):
    """
    Creates a new Vehicle under a specified customer.
    Tekmetric endpoint: POST /api/v1/vehicles :contentReference[oaicite:57]{index=57}
    """
    token   = await get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = payload.dict()
    data["shop"] = SHOP_ID

    async with httpx.AsyncClient() as client:
        # Ensure customer exists first
        cust_check = await client.get(f"{TEKMETRIC_BASE_URL}/customers/{payload.customerId}", headers=headers)
        if cust_check.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Customer ID {payload.customerId} not found")

        res = await client.post(f"{TEKMETRIC_BASE_URL}/vehicles", headers=headers, json=data)
        if res.status_code >= 400:
            raise HTTPException(status_code=res.status_code, detail=res.text)
        return res.json()


@app.patch("/api/update_vehicle/{vehicle_id}")
async def update_vehicle(vehicle_id: int, payload: VehicleUpdate):
    """
    Updates fields on an existing Vehicle.
    Tekmetric endpoint: PATCH /api/v1/vehicles/{id} :contentReference[oaicite:58]{index=58}
    """
    token   = await get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = payload.dict(exclude_unset=True)

    async with httpx.AsyncClient() as client:
        # Check vehicle existence
        check = await client.get(f"{TEKMETRIC_BASE_URL}/vehicles/{vehicle_id}", headers=headers)
        if check.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Vehicle ID {vehicle_id} not found")

        res = await client.patch(f"{TEKMETRIC_BASE_URL}/vehicles/{vehicle_id}", headers=headers, json=data)
        res.raise_for_status()
        return res.json()


@app.delete("/api/delete_vehicle/{vehicle_id}")
async def delete_vehicle(vehicle_id: int):
    """
    Deletes (archives) a Vehicle.
    Tekmetric endpoint: DELETE /api/v1/vehicles/{id} :contentReference[oaicite:59]{index=59}
    """
    token   = await get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        res = await client.delete(f"{TEKMETRIC_BASE_URL}/vehicles/{vehicle_id}", headers=headers)
        if res.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Vehicle ID {vehicle_id} not found")
        res.raise_for_status()
        return {"detail": f"Vehicle {vehicle_id} deleted successfully"}

# --- Vehicles Router ---
from routers.vehicles import router as vehicles_router
app.include_router(vehicles_router, prefix="/api/vehicles", tags=["vehicles"])
