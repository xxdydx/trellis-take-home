# Temporal Order Lifecycle System

Order processing system demonstrating Temporal workflow orchestration with fault tolerance and human-in-the-loop processes.

## Quick Start

### Prerequisites
- Python 3.8+
- Docker and Docker Compose

### Setup
```bash
git clone trellis-take-home
cd trellis-take-home
pip install -r requirements.txt
```

### Start Services
```bash
./scripts/start.sh
```

This starts Temporal server, PostgreSQL databases, workers, and FastAPI server (http://localhost:8000).

## Usage

### API Endpoints
```bash
# Start order
curl -X POST http://localhost:8000/orders/order-123/start \
  -H "Content-Type: application/json" \
  -d '{"payment_id": "payment-456"}'

# Approve order
curl -X POST http://localhost:8000/orders/order-123/signals/approve

# Cancel order
curl -X POST http://localhost:8000/orders/order-123/signals/cancel

# Update address
curl -X POST http://localhost:8000/orders/order-123/signals/update-address \
  -H "Content-Type: application/json" \
  -d '{"street": "456 Oak St", "city": "San Francisco", "state": "CA", "zip_code": "94102"}'

# Get order status
curl http://localhost:8000/orders/order-123/status
```

## Database Schema

### Tables
```sql
CREATE TABLE orders (
    id VARCHAR PRIMARY KEY,
    state VARCHAR NOT NULL DEFAULT 'received',
    address_json JSONB,
    items_json JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE payments (
    payment_id VARCHAR PRIMARY KEY,
    order_id VARCHAR REFERENCES orders(id),
    status VARCHAR NOT NULL DEFAULT 'pending',
    amount NUMERIC(10,2),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR REFERENCES orders(id),
    event_type VARCHAR NOT NULL,
    payload_json JSONB,
    timestamp TIMESTAMP DEFAULT NOW()
);
```

### Migrations
```bash
# Run database migrations
python run_migrations.py

# Test database connection
python test_connection.py
```

### Idempotency Strategy
- **Payments**: Use `payment_id` as primary key with conflict handling
- **Orders**: Use `order_id` as primary key 
- **Events**: Always append safely

## Workflow Details

### OrderWorkflow
1. **ReceiveOrder** → Creates order record
2. **ValidateOrder** → Validates order items
3. **Manual Approval** → Waits for approval signal (10s timeout)
4. **ChargePayment** → Processes payment with idempotency
5. **ShippingWorkflow** → Starts child workflow on separate queue

### ShippingWorkflow
1. **PreparePackage** → Marks package prepared
2. **DispatchCarrier** → Arranges carrier pickup
3. **ShipOrder** → Updates order to shipped

### Signals
- **CancelOrder**: Cancels workflow at any stage
- **ApproveOrder**: Proceeds past manual approval
- **UpdateAddress**: Updates shipping address

## Testing

```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/test_workflows.py::TestOrderWorkflow::test_successful_order_flow
```

Tests cover:
- Successful order completion
- Order cancellation
- Manual approval timeout
- Shipping workflow failures
- Signal handling

## Manual Setup (Alternative)

```bash
# Start Temporal server
docker run --rm -d --name temporal-dev -p 7233:7233 temporalio/auto-setup:1.22.3

# Start database
docker-compose up -d app-db
python run_migrations.py

# Start workers
python -m src.worker

# Start API
uvicorn src.api:app --port 8000
```

## Troubleshooting

### Common Issues
1. **Database errors**: Check `docker ps` - ensure PostgreSQL is running
2. **Temporal errors**: Check `docker ps | grep temporal`
3. **Slow responses**: Expected due to failure simulation

### Recovery
```bash
# Check workflow status
curl http://localhost:8000/orders/<order-id>/status

# Test database
python test_connection.py

# Initialize tables
python init_db.py
```