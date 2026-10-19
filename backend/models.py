from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from database import Base

class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String, index=True, nullable=False)
    category = Column(String, index=True)
    expiration_date = Column(String)
    added_at = Column(DateTime, default=datetime.utcnow)

class FridgeState(Base):
    __tablename__ = "fridge_state"

    id = Column(Integer, primary_key=True, index=True)
    is_online = Column(Boolean, default=True)
    last_heartbeat = Column(DateTime, default=datetime.utcnow)