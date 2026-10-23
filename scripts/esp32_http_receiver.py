"""Windows LAN relay for the existing ESP32 POST /event firmware.

The SIRO gateway owns persistence. This process only forwards a single
request and never retries after an ambiguous timeout.
"""

from __future__ import annotations

import ipaddress
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, request: Request, *args: object) -> None:
        return None


_GATEWAY_OPENER = build_opener(ProxyHandler({}), _RejectRedirects)


class RelayHandler(BaseHTTPRequestHandler):
    allowed_ip = ""
    gateway_port = 8000
    token = ""
    timeout_seconds = 0.6

    def do_POST(self) -> None:
        if self.path != "/event":
            self.send_error(404)
            return
        if self.client_address[0] != self.allowed_ip:
            self.send_error(403)
            return
        if self.headers.get_content_type() != "application/json":
            self.send_error(415)
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self.send_error(411)
            return
        if not 1 <= length <= 4096:
            self.send_error(413)
            return
        self.connection.settimeout(1.0)
        try:
            body = self.rfile.read(length)
        except TimeoutError:
            self.send_error(408)
            return
        if len(body) != length:
            self.send_error(400)
            return
        request = Request(
            f"http://127.0.0.1:{self.gateway_port}/v1/devices/esp32/events",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-SIRO-ESP32-Relay-Token": self.token,
            },
            method="POST",
        )
        try:
            with _GATEWAY_OPENER.open(request, timeout=self.timeout_seconds) as response:
                status = response.status
        except HTTPError as error:
            status = 400 if error.code == 400 else 502
        except (OSError, URLError, TimeoutError):
            # Delivery may be unknown. A POST is never retried automatically.
            status = 502
        if status != 200:
            self.send_error(status)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format: str, *args: object) -> None:
        # Sensor JSON, tokens and peer addresses must not enter default logs.
        pass


def main() -> None:
    allowed_ip = os.environ.get("SIRO_ESP32_ALLOWED_IP", "")
    try:
        address = ipaddress.ip_address(allowed_ip)
    except ValueError as error:
        raise SystemExit("SIRO_ESP32_ALLOWED_IP must be the ESP32's IP address") from error
    if address.version != 4 or address.is_loopback or address.is_unspecified:
        raise SystemExit("SIRO_ESP32_ALLOWED_IP must be an ESP32 IPv4 LAN address")
    token = os.environ.get("SIRO_ESP32_RELAY_TOKEN", "")
    if len(token) < 32:
        raise SystemExit("SIRO_ESP32_RELAY_TOKEN must contain at least 32 characters")
    try:
        gateway_port = int(os.environ.get("SIRO_GATEWAY_PORT", "8000"))
    except ValueError as error:
        raise SystemExit("SIRO_GATEWAY_PORT must be an integer") from error
    if not 1024 <= gateway_port <= 65535:
        raise SystemExit("SIRO_GATEWAY_PORT must be between 1024 and 65535")
    handler = type(
        "ConfiguredRelayHandler",
        (RelayHandler,),
        {"allowed_ip": str(address), "gateway_port": gateway_port, "token": token},
    )
    print("SIRO ESP32 relay listening on 0.0.0.0:8765/event", flush=True)
    HTTPServer(("0.0.0.0", 8765), handler).serve_forever()


if __name__ == "__main__":
    main()
