from dotenv import load_dotenv

load_dotenv()

from app import app
from routes import *


if __name__ == '__main__':
    import sys
    import os

    debug = "--debug" in sys.argv
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 80)), debug=debug, auto_reload=debug)
