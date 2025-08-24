from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Text,
    Numeric,
    ForeignKey,
    text,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

Base = declarative_base()


class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    state = Column(String, nullable=False, default="received")
    address_json = Column(JSONB)
    items_json = Column(JSONB)
    created_at = Column(DateTime, server_default=text("now()"))
    updated_at = Column(DateTime, server_default=text("now()"), onupdate=text("now()"))


class Payment(Base):
    __tablename__ = "payments"

    payment_id = Column(String, primary_key=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    status = Column(String, nullable=False, default="pending")
    amount = Column(Numeric(10, 2))
    created_at = Column(DateTime, server_default=text("now()"))
    updated_at = Column(DateTime, server_default=text("now()"), onupdate=text("now()"))


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    event_type = Column(String, nullable=False)
    payload_json = Column(JSONB)
    timestamp = Column(DateTime, server_default=text("now()"))
