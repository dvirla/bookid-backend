#!/usr/bin/env python3
"""
Database connection and table creation test script.
"""
from database import engine
from models import Base
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # Test connection
    try:
        with engine.connect() as conn:
            result = conn.execute(text('SELECT 1'))
            logger.info('✅ Database connection successful!')
    except Exception as e:
        logger.error(f'❌ Database connection failed: {e}')
        exit(1)

    # Create tables
    try:
        Base.metadata.create_all(bind=engine)
        logger.info('✅ Database tables created successfully!')
    except Exception as e:
        logger.error(f'❌ Failed to create tables: {e}')
        exit(1)

    # Check tables
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """))
            tables = [row[0] for row in result.fetchall()]
            logger.info(f'📋 Created tables: {tables}')
    except Exception as e:
        logger.error(f'❌ Failed to check tables: {e}')

    print('🎉 Database setup completed!')

if __name__ == "__main__":
    main()