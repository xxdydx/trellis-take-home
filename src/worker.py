import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker
import structlog

from .workflows import OrderWorkflow, ShippingWorkflow
from .activities import (
    receive_order_activity,
    validate_order_activity,
    charge_payment_activity,
    prepare_package_activity,
    dispatch_carrier_activity,
    ship_order_activity,
    update_address_activity_wrapper,
)
from .database.connection import create_tables

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


async def main_worker():
    """Start the main worker for order workflows"""
    logger.info("Starting main worker")

    # Initialize database tables
    await create_tables()

    # Connect to Temporal server
    client = await Client.connect("localhost:7233")

    # Create and start worker for main task queue
    worker = Worker(
        client,
        task_queue="main-tq",
        workflows=[OrderWorkflow],
        activities=[
            receive_order_activity,
            validate_order_activity,
            charge_payment_activity,
            update_address_activity_wrapper,
        ],
    )

    logger.info("Main worker started, listening on main-tq")
    await worker.run()


async def shipping_worker():
    """Start the shipping worker for shipping workflows"""
    logger.info("Starting shipping worker")

    # Connect to Temporal server
    client = await Client.connect("localhost:7233")

    # Create and start worker for shipping task queue
    worker = Worker(
        client,
        task_queue="shipping-tq",
        workflows=[ShippingWorkflow],
        activities=[
            prepare_package_activity,
            dispatch_carrier_activity,
            ship_order_activity,
        ],
    )

    logger.info("Shipping worker started, listening on shipping-tq")
    await worker.run()


async def run_all_workers():
    """Run both workers concurrently"""
    logger.info("Starting all workers")

    # Run both workers concurrently
    await asyncio.gather(
        main_worker(),
        shipping_worker(),
    )


if __name__ == "__main__":
    asyncio.run(run_all_workers())
