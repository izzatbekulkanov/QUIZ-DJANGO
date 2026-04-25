import os
import sys
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, make_server


BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

from core.startup import apply_runtime_patches

apply_runtime_patches()

from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.wsgi import get_wsgi_application


class Handler(WSGIRequestHandler):
    def log_message(self, format, *args):
        sys.stderr.write(
            "%s - - [%s] %s\n"
            % (self.address_string(), self.log_date_time_string(), format % args)
        )
        sys.stderr.flush()


def main():
    host = os.getenv("DEV_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("DEV_SERVER_PORT", "8000"))
    app = StaticFilesHandler(get_wsgi_application())
    httpd = make_server(host, port, app, handler_class=Handler)
    print(f"Serving on http://{host}:{port}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
