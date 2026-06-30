#!/usr/bin/env python3
"""
amazon_ads.py — LIVE Amazon Advertising API (your real ad spend, sales, ACOS).

Same LWA auth as SP-API, but a separate app + separate token, and every call also needs
your advertising PROFILE id and the client id as `Amazon-Advertising-API-ClientId`.

Campaign spend/sales come from the Reporting API, which is asynchronous (request a report,
poll until ready, download). `request_sp_report` kicks it off; wire the poll/download once
you have a live profile (the response shape is account-specific). For a first pass,
`list_campaigns` confirms the connection and lists what's running.

Secrets (see SETUP.md):
  ADS_REFRESH_TOKEN · ADS_CLIENT_ID · ADS_CLIENT_SECRET · ADS_PROFILE_ID
"""
from __future__ import annotations

from . import config
from .base import request_json, AdapterError

LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
ADS_HOSTS = {
    "na": "https://advertising-api.amazon.com",
    "eu": "https://advertising-api-eu.amazon.com",
    "fe": "https://advertising-api-fe.amazon.com",
}


class AdsApiClient:
    def __init__(self, region="na", refresh_token=None, client_id=None,
                 client_secret=None, profile_id=None):
        self.host = ADS_HOSTS.get(region, ADS_HOSTS["na"])
        self.refresh_token = refresh_token or config.get("ADS_REFRESH_TOKEN")
        self.client_id = client_id or config.get("ADS_CLIENT_ID")
        self.client_secret = client_secret or config.get("ADS_CLIENT_SECRET")
        self.profile_id = profile_id or config.get("ADS_PROFILE_ID")
        if not all((self.refresh_token, self.client_id, self.client_secret)):
            raise AdapterError("Ads creds missing (ADS_REFRESH_TOKEN/CLIENT_ID/CLIENT_SECRET)")
        self._access_token = None

    def _token(self):
        if self._access_token:
            return self._access_token
        data = request_json("POST", LWA_TOKEN_URL, form={
            "grant_type": "refresh_token", "refresh_token": self.refresh_token,
            "client_id": self.client_id, "client_secret": self.client_secret,
        })
        self._access_token = data["access_token"]
        return self._access_token

    def _headers(self):
        h = {"Amazon-Advertising-API-ClientId": self.client_id,
             "Authorization": "Bearer " + self._token()}
        if self.profile_id:
            h["Amazon-Advertising-API-Scope"] = str(self.profile_id)
        return h

    def check(self):
        """Lists ad profiles on the account — proves the token + client id work."""
        return request_json("GET", self.host + "/v2/profiles", headers=self._headers())

    def list_campaigns(self):
        """Sponsored Products campaigns currently configured."""
        return request_json("GET", self.host + "/sp/campaigns", headers=self._headers(),
                            json_body=None) or []
