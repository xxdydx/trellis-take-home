from datetime import datetime, UTC
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from temporalio.client import Client
import structlog

from .workflows import OrderWorkflow
from .database.connection import get_db_session
from .database.models import Order
from sqlalchemy import select

logger = structlog.get_logger()


# Pydantic models for requests
class StartOrderRequest(BaseModel):
    payment_id: str
    items: list = None
    address: Dict[str, Any] = None


class UpdateAddressRequest(BaseModel):
    street: str
    city: str
    state: str
    zip_code: str
    country: str = "US"


class OrderResponse(BaseModel):
    order_id: str
    status: str
    message: str
    workflow_id: Optional[str] = None


# Global client instance
temporal_client = None


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Manage application lifespan"""
    # Startup
    global temporal_client
    temporal_client = await Client.connect("localhost:7233")
    logger.info("Connected to Temporal server")

    # Initialize database tables
    try:
        from .database.connection import create_tables

        await create_tables()
        logger.info("Database tables initialized")
    except Exception as e:
        logger.warning(
            "Database tables initialization failed - they may already exist",
            error=str(e),
        )
        # Don't fail startup - the tables might already exist

    yield

    # Shutdown
    if temporal_client:
        # Temporal client doesn't need explicit close in newer versions
        pass


# Create the FastAPI app
app = FastAPI(title="Order Lifecycle API", version="1.0.0", lifespan=lifespan)


@app.post("/orders/{order_id}/start", response_model=OrderResponse)
async def start_order(order_id: str, request: StartOrderRequest):
    """Start an order workflow"""
    try:
        workflow_id = f"order-{order_id}"

        # Start the workflow
        await temporal_client.start_workflow(
            OrderWorkflow.run,
            args=[order_id, request.payment_id, request.items, request.address],
            id=workflow_id,
            task_queue="main-tq",
        )

        logger.info(
            "Started order workflow", order_id=order_id, workflow_id=workflow_id
        )

        return OrderResponse(
            order_id=order_id,
            status="started",
            message="Order workflow started successfully",
            workflow_id=workflow_id,
        )

    except Exception as e:
        logger.error("Failed to start order workflow", order_id=order_id, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to start workflow: {str(e)}"
        )


@app.post("/orders/{order_id}/signals/cancel", response_model=OrderResponse)
async def cancel_order(order_id: str):
    """Send cancel signal to order workflow"""
    try:
        workflow_id = f"order-{order_id}"
        handle = temporal_client.get_workflow_handle(workflow_id)

        await handle.signal(OrderWorkflow.cancel_order)

        logger.info("Sent cancel signal", order_id=order_id, workflow_id=workflow_id)

        return OrderResponse(
            order_id=order_id,
            status="cancel_sent",
            message="Cancel signal sent to workflow",
        )

    except Exception as e:
        logger.error("Failed to cancel order", order_id=order_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to cancel order: {str(e)}")


@app.post("/orders/{order_id}/signals/approve", response_model=OrderResponse)
async def approve_order(order_id: str):
    """Send approval signal to order workflow"""
    try:
        workflow_id = f"order-{order_id}"
        handle = temporal_client.get_workflow_handle(workflow_id)

        await handle.signal(OrderWorkflow.approve_order)

        logger.info("Sent approval signal", order_id=order_id, workflow_id=workflow_id)

        return OrderResponse(
            order_id=order_id,
            status="approval_sent",
            message="Approval signal sent to workflow",
        )

    except Exception as e:
        logger.error("Failed to approve order", order_id=order_id, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to approve order: {str(e)}"
        )


@app.post("/orders/{order_id}/signals/update-address", response_model=OrderResponse)
async def update_address(order_id: str, request: UpdateAddressRequest):
    """Send address update signal to order workflow"""
    try:
        workflow_id = f"order-{order_id}"
        handle = temporal_client.get_workflow_handle(workflow_id)

        address_data = request.model_dump()
        await handle.signal(OrderWorkflow.update_address, address_data)

        logger.info(
            "Sent address update signal", order_id=order_id, address=address_data
        )

        return OrderResponse(
            order_id=order_id,
            status="address_update_sent",
            message="Address update signal sent to workflow",
        )

    except Exception as e:
        logger.error("Failed to update address", order_id=order_id, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to update address: {str(e)}"
        )


@app.get("/orders/{order_id}/status")
async def get_order_status(order_id: str):
    """Get current order status from workflow and database"""
    try:
        workflow_id = f"order-{order_id}"

        # Get workflow status
        workflow_status = {}
        try:
            handle = temporal_client.get_workflow_handle(workflow_id)
            workflow_status = await handle.query(OrderWorkflow.get_status)
        except Exception as e:
            logger.warning(
                "Could not get workflow status", order_id=order_id, error=str(e)
            )
            workflow_status = {"error": "Workflow not found or not running"}

        # Get database status
        db_status = {}
        async with get_db_session() as session:
            result = await session.execute(select(Order).where(Order.id == order_id))
            order = result.scalar_one_or_none()
            if order:
                db_status = {
                    "order_id": order.id,
                    "state": order.state,
                    "items": order.items_json,
                    "address": order.address_json,
                    "created_at": (
                        order.created_at.isoformat() if order.created_at else None
                    ),
                    "updated_at": (
                        order.updated_at.isoformat() if order.updated_at else None
                    ),
                }
            else:
                db_status = {"error": "Order not found in database"}

        return {
            "order_id": order_id,
            "workflow_status": workflow_status,
            "database_status": db_status,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        logger.error("Failed to get order status", order_id=order_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now(UTC).isoformat()}


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Order Lifecycle API",
        "version": "1.0.0",
        "endpoints": {
            "start_order": "POST /orders/{order_id}/start",
            "cancel_order": "POST /orders/{order_id}/signals/cancel",
            "approve_order": "POST /orders/{order_id}/signals/approve",
            "update_address": "POST /orders/{order_id}/signals/update-address",
            "get_status": "GET /orders/{order_id}/status",
            "health": "GET /health",
        },
    }
