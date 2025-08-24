-- Initial schema for Order Lifecycle System
-- Migration: 001_initial_schema.sql

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    id VARCHAR PRIMARY KEY,
    state VARCHAR NOT NULL DEFAULT 'received',
    address_json JSONB,
    items_json JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Payments table (idempotent via payment_id PK)
CREATE TABLE IF NOT EXISTS payments (
    payment_id VARCHAR PRIMARY KEY,
    order_id VARCHAR REFERENCES orders(id),
    status VARCHAR NOT NULL DEFAULT 'pending',
    amount NUMERIC(10,2),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Events table (for debugging/auditing)
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR REFERENCES orders(id),
    event_type VARCHAR NOT NULL,
    payload_json JSONB,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_orders_state ON orders(state);
CREATE INDEX IF NOT EXISTS idx_payments_order_id ON payments(order_id);
CREATE INDEX IF NOT EXISTS idx_events_order_id ON events(order_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);