# Necessary configuration BEFORE loading app

import sys
import os
import logging
from dotenv import load_dotenv

load_dotenv()

DEBUG = "--debug" in sys.argv

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="[%(asctime)s %(name)s:%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# configure access logs
# they require a different format, and should be disabled
# in production mode
access = logging.getLogger("sanic.access")
access.propagate = False
if not DEBUG:
    access.disabled = True
else:
    handler = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s - %(name)s:%(levelname)s][%(host)s]: "
        + "%(request)s %(message)s %(status)s %(byte)s",
    )
    handler.setFormatter(formatter)
    access.addHandler(handler)

from app import app
from routes import *


if __name__ == '__main__':
    from sanic.http.constants import HTTP

    app.run(
        host="0.0.0.0", 
        port=int(os.environ.get("PORT", 80)), 
        debug=DEBUG, 
        auto_reload=DEBUG,
        access_log=DEBUG,
        # protocol=HTTP.VERSION_3
    )
