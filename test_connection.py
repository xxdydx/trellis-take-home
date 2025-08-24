#!/usr/bin/env python3
"""
Test database connection for troubleshooting
"""

import asyncio
import sys
import os
from sqlalchemy.exc import SQLAlchemyError

# Add the src directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database.connection import get_db_session, engine


async def test_connection():
    """Test database connection"""
    print("🔍 Testing database connection...")
    print(f"Database URL: {engine.url}")
    
    try:
        # Test basic connection
        async with get_db_session() as session:
            result = await session.execute("SELECT 1")
            await result.fetchall()
            print("✅ Database connection successful!")
            
        # Test table creation
        from src.database.connection import create_tables
        await create_tables()
        print("✅ Table creation successful!")
        
        return True
        
    except SQLAlchemyError as e:
        print(f"❌ Database error: {e}")
        print("💡 Troubleshooting steps:")
        print("   1. Check if PostgreSQL is running:")
        print("      docker ps | grep postgres")
        print("   2. Start the database:")
        print("      docker-compose up -d app-db")
        print("   3. Check if the database is accessible:")
        print("      docker exec -it app-postgres psql -U orders -d orders -c 'SELECT 1'")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


async def main():
    success = await test_connection()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())