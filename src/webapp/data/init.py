from .base import Base, engine
from .users import register_user, UserExistsException
import os
import logging

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from sanic import Sanic

logger = logging.getLogger(__name__)


async def init_db(app: 'Sanic', loop):
    logger.info("Initializing DB")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        await register_user(os.environ.get("ADMIN_USER", "admin"), os.environ["PASSWORD"], force_verified=True)
        logger.info("Admin user created")
    except UserExistsException:
        logger.info("Admin user already exists")
