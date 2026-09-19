"""Serialize guest registration and respect upstream rate limits in this process."""
import math
import threading
import time
from email.utils import parsedate_to_datetime

import requests


class RegistrationCooldown(requests.RequestException):
    def __init__(self, seconds):
        super().__init__("Guest registration is paused after a rate limit")
        self.retry_after_seconds = seconds


class RegistrationGate:
    def __init__(self, interval=5, fallback_cooldown=60):
        self.interval = interval
        self.fallback_cooldown = fallback_cooldown
        self.next_request = 0
        self.lock = threading.Lock()

    def post(self, session, url, **kwargs):
        with self.lock:
            remaining = math.ceil(self.next_request - time.monotonic())
            if remaining > 0:
                raise RegistrationCooldown(remaining)
            # Space requests even when the connection fails or times out.
            self.next_request = time.monotonic() + self.interval
            response = session.post(url, **kwargs)
            limited = response.status_code == 429
            try:
                body = response.json()
                limited = limited or (isinstance(body, dict) and (
                    str(body.get('code')) == '1006' or body.get('error') == 'error_too_many_requests'))
            except ValueError:
                pass
            if limited:
                delay = self.fallback_cooldown
                retry_after = response.headers.get('Retry-After', '')
                try:
                    delay = max(0, int(retry_after))
                except (TypeError, ValueError):
                    if isinstance(retry_after, str) and retry_after:
                        try:
                            delay = max(0, math.ceil(parsedate_to_datetime(retry_after).timestamp() - time.time()))
                        except (TypeError, ValueError, OverflowError):
                            pass
                delay = max(self.interval, delay)
                self.next_request = time.monotonic() + delay
                response.registration_retry_after_seconds = delay
            return response


REGISTRATION_GATE = RegistrationGate()
