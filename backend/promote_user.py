import asyncio
import logging
import sys
from sqlalchemy import select
from app.core.database import async_session_maker
from app.models.user import User

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("promote_user")

async def main():
    async with async_session_maker() as session:
        logger.info("Connecting to database to promote user...")
        query = select(User).where(User.email == "demo_admin@democorp.com")
        res = await session.execute(query)
        user = res.scalar_one_or_none()
        
        if not user:
            logger.error("User demo_admin@democorp.com not found!")
            sys.exit(1)
            
        logger.info(f"Found user: {user.first_name} {user.last_name} with current role: {user.role}")
        user.role = "SuperAdmin"
        await session.commit()
        logger.info("Successfully updated user role to SuperAdmin!")

if __name__ == "__main__":
    asyncio.run(main())
