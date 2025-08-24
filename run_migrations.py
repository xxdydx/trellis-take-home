#!/usr/bin/env python3
"""
Database migration runner for Order Lifecycle System
"""

import asyncio
import sys
import os
from pathlib import Path
from sqlalchemy.sql import text

# Add the src directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database.connection import get_db_session


async def run_migration(migration_file: Path):
    """Run a single migration file"""
    print(f"Running migration: {migration_file.name}")
    
    with open(migration_file, 'r') as f:
        sql_content = f.read()
    
    async with get_db_session() as session:
        # Split by semicolon and execute each statement
        statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
        
        for statement in statements:
            if statement.strip():
                await session.execute(text(statement))
        
        await session.commit()
    
    print(f"✅ Migration {migration_file.name} completed")


async def run_migrations():
    """Run all migration files in order"""
    migrations_dir = Path(__file__).parent / "migrations"
    
    if not migrations_dir.exists():
        print("❌ Migrations directory not found")
        return False
    
    # Get all SQL files and sort them
    migration_files = sorted(migrations_dir.glob("*.sql"))
    
    if not migration_files:
        print("ℹ️  No migration files found")
        return True
    
    print(f"🗄️  Running {len(migration_files)} migrations...")
    
    try:
        for migration_file in migration_files:
            await run_migration(migration_file)
        
        print("✅ All migrations completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False


async def main():
    """Main migration runner"""
    success = await run_migrations()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())