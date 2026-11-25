import asyncio

from sqlalchemy import delete, select

from app.database.connection import SessionLocal, dispose_engine
from app.models.company import Company
from app.models.job import Job


async def main() -> None:
    async with SessionLocal() as session:
        company = await session.scalar(
            select(Company).where(Company.company_slug == "stripe")
        )
        if company is None:
            print("stripe company not found")
            return
        result = await session.execute(
            delete(Job).where(Job.company_id == company.company_id)
        )
        await session.commit()
        print(f"deleted {result.rowcount} jobs for {company.company_name}")
    await dispose_engine()


asyncio.run(main())
