#!/bin/bash

# Start Order Lifecycle System
echo "🚀 Starting Order Lifecycle System..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Start databases and Temporal server
echo "📦 Starting databases and Temporal server..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Check if Temporal is ready by checking if port is listening
echo "🔍 Checking Temporal server..."
timeout=30
while [ $timeout -gt 0 ]; do
    if docker exec temporal-server netstat -tln | grep -q ":7233 "; then
        echo "✅ Temporal server is ready"
        break
    fi
    echo "Waiting for Temporal server... ($timeout seconds remaining)"
    sleep 2
    timeout=$((timeout-2))
done

if [ $timeout -le 0 ]; then
    echo "❌ Temporal server failed to start"
    exit 1
fi

# Run database migrations
echo "🗄️  Running database migrations..."
python3 run_migrations.py

# Start workers in background
echo "👷 Starting workers..."
python3 -m src.worker &
WORKER_PID=$!

# Check if port 8000 is already in use and find an available port
API_PORT=8000
while lsof -Pi :$API_PORT -sTCP:LISTEN -t >/dev/null 2>&1; do
    echo "⚠️  Port $API_PORT is already in use, trying next port..."
    API_PORT=$((API_PORT + 1))
    if [ $API_PORT -gt 8010 ]; then
        echo "❌ Could not find an available port between 8000-8010"
        exit 1
    fi
done

# Start API server
echo "🌐 Starting API server on port $API_PORT..."
uvicorn src.api:app --host 0.0.0.0 --port $API_PORT &
API_PID=$!

echo "✅ All services started successfully!"
echo ""
echo "🔗 Services:"
echo "  - Temporal Server: localhost:7233 (gRPC)"
echo "  - API Server: http://localhost:$API_PORT"
echo "  - API Docs: http://localhost:$API_PORT/docs"
echo ""
echo "📝 API Endpoints:"
echo "  POST /orders/{order_id}/start - Start an order workflow"
echo "  POST /orders/{order_id}/approve - Approve an order"
echo "  POST /orders/{order_id}/cancel - Cancel an order"
echo "  POST /orders/{order_id}/update-address - Update shipping address"
echo "  GET /orders/{order_id}/status - Get order status"
echo ""
echo "Press Ctrl+C to stop all services"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    kill $WORKER_PID 2>/dev/null
    kill $API_PID 2>/dev/null
    docker-compose down
    echo "✅ All services stopped"
}

# Set trap to cleanup on exit
trap cleanup EXIT INT TERM

# Wait for user to stop
wait 