"""Límite de solicitudes por IP (429 rate_limited)."""

from unittest import mock

from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

from telemetry.throttling import ClientIpRateThrottle

from .test_contract import ContractTestCase

LOW_RATES = {"telemetry": "2/min", "stats": "2/min"}


@mock.patch.dict(ClientIpRateThrottle.THROTTLE_RATES, LOW_RATES)
@override_settings(CLIENT_IP_HEADER="HTTP_CF_CONNECTING_IP")
class ThrottlingTests(ContractTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def health(self, ip, forwarded=None):
        headers = {"HTTP_X_API_KEY": self.key, "HTTP_CF_CONNECTING_IP": ip}
        if forwarded:
            headers["HTTP_X_FORWARDED_FOR"] = forwarded
        return APIClient().get("/v1/health", **headers)

    def test_limits_by_client_ip(self):
        self.assertEqual(self.health("203.0.113.1").status_code, 200)
        self.assertEqual(self.health("203.0.113.1").status_code, 200)
        self.assertContractError(self.health("203.0.113.1"), 429, "rate_limited")
        # Otra persona no comparte el límite
        self.assertEqual(self.health("203.0.113.2").status_code, 200)

    def test_forged_forwarded_for_does_not_help(self):
        for fake in ("1.1.1.1", "2.2.2.2", "3.3.3.3"):
            response = self.health("203.0.113.1", forwarded=fake)
        self.assertContractError(response, 429, "rate_limited")

    def test_dashboard_has_its_own_limit(self):
        self.health("203.0.113.1")
        self.health("203.0.113.1")
        response = APIClient().get("/stats/v1/simulations", HTTP_CF_CONNECTING_IP="203.0.113.1")
        self.assertEqual(response.status_code, 200)
