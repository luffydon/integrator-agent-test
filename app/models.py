from sqlalchemy import Column, Integer, String, DateTime, JSON, Float
from sqlalchemy.sql import func
from app.db import Base

class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    service_name = Column(String, nullable=False)
    requested_time = Column(DateTime, nullable=True)
    channel = Column(String, nullable=True)  # 'telegram' or 'http'
    price = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    attributes = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
