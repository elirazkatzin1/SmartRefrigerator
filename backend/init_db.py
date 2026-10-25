import asyncio
from sqlalchemy import text
from database import engine, Base
import models

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # create_all does not add new columns to tables that already exist
        await conn.execute(text(
            "ALTER TABLE fridge_state ADD COLUMN IF NOT EXISTS last_image_taken TIMESTAMP"
        ))
        # expiration_date used to be a string column; convert it so it can be compared as a date
        await conn.execute(text("""
            DO $$
            BEGIN
                IF (SELECT data_type FROM information_schema.columns
                    WHERE table_name = 'inventory' AND column_name = 'expiration_date') <> 'date' THEN
                    ALTER TABLE inventory ALTER COLUMN expiration_date TYPE DATE USING expiration_date::date;
                END IF;
            END $$;
        """))
    print("Database tables created successfully.")

if __name__ == "__main__":
    asyncio.run(init_db())
