import logging
import os
import sys

import uvicorn
from dotenv import load_dotenv

load_dotenv()

from .app import app
from .routes import (
    add_error_handlers,
    admin_router,
    public_router,
    user_router,
)

DEBUG = "--debug" in sys.argv

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="[%(asctime)s %(name)s:%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

add_error_handlers(app)

# Order matters here, the 'admin_router' has update routes which should take precedence
# over any public user-facing routes (e.g. recipes with pretty names for example)
app.include_router(admin_router)
app.include_router(public_router)
app.include_router(user_router)


def main():
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 80)),  # noqa: PLW1508
        # needed for full-url POST requests from JS
        proxy_headers=True,
        forwarded_allow_ips="*",
        # reload=DEBUG,
        access_log=DEBUG,
    )


if __name__ == "__main__":
    main()
