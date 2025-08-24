#!/usr/bin/env python3
"""
Database initialization script for the Order Lifecycle system
"""

import asyncio
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database.connection import create_tables


async def main():
    """Initialize database tables"""
    print("🗄️  Initializing database tables...")
    
    try:
        await create_tables()
        print("✅ Database tables created successfully!")
        
        # Test the connection by importing models
        from src.database.models import Order, Payment, Event
        print(f"✅ Models loaded: {Order.__tablename__}, {Payment.__tablename__}, {Event.__tablename__}")
        
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        print(f"💡 Make sure PostgreSQL is running:")
        print(f"   docker-compose up -d app-db")
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)