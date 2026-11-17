#!/usr/bin/env python3
"""Read quota from a New API compatible gateway without storing credentials."""

import argparse
import json
import math
import os
import sys
import urllib.parse
import urllib.request


def amount(value, units, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} is missing or invalid")
    return round(max(0, value) / units, 2)


def normalize_token(payload, units):
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or payload.get("code") is not True or not isinstance(data, dict):
        raise ValueError("gateway did not return token quota data")
    unlimited = data.get("unlimited_quota") is True
    user_quota = data.get("user_quota")
    embedded = user_quota.get("total_available") if isinstance(user_quota, dict) else None
    return {
        "unlimited": unlimited,
        "remaining": None if unlimited else amount(data.get("total_available"), units, "token remaining quota"),
        "account_remaining": amount(embedded, units, "account remaining quota") if embedded is not None else None,
        "used": amount(data["total_used"], units, "used quota") if "total_used" in data else None,
        "granted": amount(data["total_granted"], units, "granted quota") if "total_granted" in data else None,
        "expires_at": data.get("expires_at") if isinstance(data.get("expires_at"), (int, float)) and not isinstance(data.get("expires_at"), bool) else None,
    }


def normalize_account(payload, units):
    data = payload.get("data") if isinstance(payload, dict) and payload.get("success") is True else None
    if not isinstance(data, dict):
        raise ValueError("gateway did not return account quota data")
    return amount(data.get("quota"), units, "account quota")


def gateway_url(base_url):
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ValueError("base URL must be an http(s) origin without a path or credentials")
    if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("remote gateway must use HTTPS")
    return base_url.rstrip("/")


def get_json(url, headers=None, timeout=10):
    request = urllib.request.Request(url, headers={"Accept": "application/json", **(headers or {})})
    class SameOriginRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, original, fp, code, msg, redirect_headers, newurl):
            old = urllib.parse.urlsplit(original.full_url)
            new = urllib.parse.urlsplit(newurl)
            if (new.scheme, new.netloc) != (old.scheme, old.netloc):
                raise ValueError("gateway redirected to another origin")
            return super().redirect_request(original, fp, code, msg, redirect_headers, newurl)
    opener = urllib.request.build_opener(SameOriginRedirect)
    with opener.open(request, timeout=timeout) as response:
        return json.load(response)


def fetch(base_url, api_key, account_token=None, user_id=None, get=get_json):
    if not api_key:
        raise ValueError("API key is required")
    if bool(account_token) != bool(user_id):
        raise ValueError("account token and user ID must be supplied together")
    if user_id and (not str(user_id).isdigit() or int(user_id) <= 0):
        raise ValueError("user ID must be a positive integer")
    base = gateway_url(base_url)
    status = get(base + "/api/status")
    units = (status.get("data") or {}).get("quota_per_unit") if isinstance(status, dict) else None
    if isinstance(units, bool) or not isinstance(units, (int, float)) or units <= 0:
        raise ValueError("gateway did not return a valid quota_per_unit")
    payload = get(base + "/api/usage/token/", {"Authorization": "Bearer " + api_key})
    result = normalize_token(payload, units)
    if account_token:
        account = get(base + "/api/user/self", {
            "Authorization": "Bearer " + account_token,
            "New-Api-User": str(user_id),
        })
        result["account_remaining"] = normalize_account(account, units)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("GATEWAY_BASE_URL"), help="Gateway origin; or GATEWAY_BASE_URL")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)
    if not args.base_url:
        parser.error("set --base-url or GATEWAY_BASE_URL")
    try:
        result = fetch(args.base_url, os.environ.get("GATEWAY_API_KEY"),
                       os.environ.get("GATEWAY_ACCOUNT_TOKEN"), os.environ.get("GATEWAY_USER_ID"))
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"quota check failed: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print("Token: unlimited" if result["unlimited"] else f"Token remaining: {result['remaining']:.2f}")
        if result["account_remaining"] is not None:
            print(f"Account remaining: {result['account_remaining']:.2f}")
        if result["used"] is not None:
            print(f"Used: {result['used']:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
