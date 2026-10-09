"""Credential-safe standalone API probe regression tests."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from scripts import nio_api_probe


def test_probe_never_follows_redirect_with_bearer_token(
    monkeypatch, capsys, socket_enabled
) -> None:
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            if self.path.endswith("/latest"):
                self.send_response(302)
                self.send_header("Location", "/other-host-or-endpoint")
            else:
                self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"result_code":"success","data":{}}')

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(
        nio_api_probe, "BASE_URL", f"http://127.0.0.1:{server.server_port}/"
    )
    try:
        nio_api_probe.probe("synthetic-vin", "synthetic-token", "latest", None)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert requests == ["/synthetic-vin/vehicle_status/latest"]
    output = capsys.readouterr().out
    assert "synthetic-token" not in output
    assert "synthetic-vin" not in output
    assert json.loads(output)["http_status"] == 302
