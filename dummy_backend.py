import asyncio
from fastapi import FastAPI, Request
from typing import Any, Dict

# Create a FastAPI instance for our dummy backend
app = FastAPI()

# This endpoint mimics the GET /api/services/ endpoint
@app.get("/api/services")
async def list_services():
    """Returns a hardcoded list of food services."""
    print("--> Dummy Backend: Received request for /api/services")
    await asyncio.sleep(0.1)  # Simulate network delay
    return [
        {"id": 101, "name": "Dummy Pizza", "price": 15.00, "currency": "USD", "flow_key": "food"},
        {"id": 102, "name": "Dummy Burger", "price": 10.50, "currency": "USD", "flow_key": "food"},
        {"id": 103, "name": "Dummy Salad", "price": 8.00, "currency": "USD", "flow_key": "food"},
    ]

# This endpoint mimics the POST /api/bookings/ endpoint
@app.post("/api/bookings")
async def create_booking(request: Request):
    """Receives a booking, prints it, and returns a success message."""
    booking_data: Dict[str, Any] = await request.json()
    print("\n--- Dummy Backend: Received New Booking! ---")
    print(booking_data)
    print("------------------------------------------\n")
    await asyncio.sleep(0.1)  # Simulate network delay
    return {"status": "ok", "booking_id": 12345}

print("Dummy backend is ready to run.")