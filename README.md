# Gateway Quota Check

A small, local quota checker extracted from a chat panel. It reads token quota and, optionally, account balance from a New API compatible gateway. It checks the gateway's `quota_per_unit` instead of assuming a fixed conversion value. Credentials are read from environment variables and are never saved by this tool.

Requires Python 3.9 or newer. No third-party packages.

```sh
export GATEWAY_BASE_URL='https://your-gateway.example'
export GATEWAY_API_KEY='your-api-key'
python3 quota_check.py
```

For the account balance too, set both `GATEWAY_ACCOUNT_TOKEN` and `GATEWAY_USER_ID`. Use `--json` for structured output. The base URL can also be passed with `--base-url`. Remote gateways must use HTTPS; HTTP is accepted for localhost.

The tool reads `/api/status`, `/api/usage/token/`, and optionally `/api/user/self`. Gateway implementations may differ in their response shape. A missing or malformed balance causes an error instead of a guessed value. An unlimited token shows `unlimited` rather than a negative remaining balance.

Run tests:

```sh
python3 -m unittest discover -s tests -v
```

MIT licensed. See [LICENSE](LICENSE).
