#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Suburb Intel Backend Startup Script
Initialize database and start API server
"""
import sys
from pathlib import Path

# Add backend directory to path for imports
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir.parent))  # Add parent (suburb-intel) to path
sys.path.insert(1, str(backend_dir))         # Add backend dir itself


def init_and_seed_database():
    """Initialize and seed the database"""
    print("=" * 60)
    print("SUBURB INTEL - Database Initialization")
    print("=" * 60)
    
    try:
        from app.db.session import init_db, sync_engine
        from app.db import models
        
        # Drop existing tables and recreate with new schema
        Base = models.Base
        Base.metadata.drop_all(bind=sync_engine)
        Base.metadata.create_all(bind=sync_engine)
        print("✓ Database schema created")
        
        # Now seed data
        from app.db.init_db import seed_database_sync
        seed_database_sync()
        print("\n✓ Database seeded successfully!")
        return True
    except Exception as e:
        print(f"\n✗ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\nStarting Suburb Intel Backend...")
    
    # Seed database first
    if not init_and_seed_database():
        print("\n⚠ Warning: Database seeding may have issues. Continuing anyway...")
    
    print("\nBackend ready!")
    print("Run 'uvicorn app.main:app --reload --host 0.0.0.0 --port 8000' to start server")


if __name__ == "__main__":
    main()
