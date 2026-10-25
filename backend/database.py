import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

# כתובת החיבור לפוסטגרס - שימי לב לתחילית postgresql+asyncpg
# אם את רצה בתוך דוקר, ה-localhost יתחלף בשם השירות (למשל 'db')
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://smart_user:smart_password@localhost:5432/smart_fridge"
)

# יצירת המנוע האסינכרוני
engine = create_async_engine(DATABASE_URL, echo=True)

# יצירת מייצר סשנים אסינכרוניים
AsyncSessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

Base = declarative_base()


# FastAPI dependency: opens a session per request and closes it afterwards
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
