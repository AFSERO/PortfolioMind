"""Small GET-only transport for three fixed public data services; no redirects."""

import http.client
import re
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit

from investment_intelligence.providers import ProviderError, DataUnavailableError

_SEC_LOCK = threading.Lock()
_SEC_LAST_REQUEST = 0.0


def throttle_sec():
    """At most two request starts/second across provider instances in this process."""
    global _SEC_LAST_REQUEST
    with _SEC_LOCK:
        delay = max(0.0, 0.5 - (time.monotonic() - _SEC_LAST_REQUEST))
        if delay:
            time.sleep(delay)
        _SEC_LAST_REQUEST = time.monotonic()


def allowed_url(url):
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.username or parts.password or parts.port is not None or parts.fragment:
        return False
    paths = {
        "query1.finance.yahoo.com": r"/v8/finance/chart/[A-Z0-9.-]{1,16}",
        "news.google.com": r"/rss/search",
        "www.sec.gov": r"/files/company_tickers.json",
        "data.sec.gov": r"/submissions/CIK[0-9]{10}\.json",
    }
    pattern = paths.get(parts.hostname)
    return bool(pattern and re.fullmatch(pattern, parts.path))


class BoundedHTTPClient:
    """Standard-library HTTPS avoids a new dependency. Body is capped before parsing."""

    def __init__(self, *, connect_timeout=5.0, read_timeout=10.0, max_bytes=4_000_000):
        if not 0 < connect_timeout <= 30 or not 0 < read_timeout <= 30 or not 0 < max_bytes <= 8_000_000:
            raise ValueError("Invalid HTTP bounds")
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.max_bytes = max_bytes

    def get(self, url, *, headers=None):
        try:
            if not allowed_url(url):
                raise ProviderError("unsupported_endpoint")
            parts = urlsplit(url)
        except ValueError:
            raise ProviderError("unsupported_endpoint") from None
        if parts.hostname in {"www.sec.gov", "data.sec.gov"}:
            throttle_sec()
        connection = http.client.HTTPSConnection(parts.hostname, timeout=self.connect_timeout,
                                                context=ssl.create_default_context())
        try:
            connection.connect()
            connection.sock.settimeout(self.read_timeout)
            request_headers = {"User-Agent": "InvestmentIntelligence/0.1", "Accept-Encoding": "identity"}
            request_headers.update(headers or {})
            connection.request("GET", parts.path + ("?" + parts.query if parts.query else ""),
                               headers=request_headers)
            response = connection.getresponse()
            if response.status == 404:
                raise DataUnavailableError("not_found")
            if response.status != 200:  # Including redirects, 403 and 429; never follow/retry.
                raise ProviderError("http_error")
            if response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise ProviderError("unsupported_encoding")
            length = response.getheader("Content-Length")
            if length is not None and (not length.isdigit() or int(length) > self.max_bytes):
                raise ProviderError("response_too_large")
            chunks, size = [], 0
            deadline = time.monotonic() + self.read_timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ProviderError("timeout")
                # read1 performs at most one underlying read, so slow trickles are bounded.
                if connection.sock is not None:
                    connection.sock.settimeout(min(self.read_timeout, remaining))
                chunk = response.read1(min(65536, self.max_bytes + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > self.max_bytes:
                    raise ProviderError("response_too_large")
            return b"".join(chunks)
        except (socket.timeout, TimeoutError):
            raise ProviderError("timeout") from None
        except (OSError, http.client.HTTPException, ValueError):
            raise ProviderError("transport_error") from None
        finally:
            connection.close()
