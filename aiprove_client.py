"""Shared AIProve client: curl-based HTTP (urllib gets 403/timeouts on
aiprove.fun), EIP-191 auth, keypair from env/file only. No secrets logged."""

import json
import os
import subprocess

API_BASE = os.environ.get("API_BASE_URL", "https://aiprove.fun")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"


def log(msg):
    print(f"[aiprove] {msg}", flush=True)


def curl_json(method, path, data=None, token=None, raw=False):
    url = API_BASE + path if path.startswith("/") else path
    cmd = ["curl", "-s", "-A", UA, "-X", method, url,
           "-w", "\nHTTP_CODE:%{http_code}"]
    if data is not None:
        cmd += ["-H", "content-type: application/json", "-d", json.dumps(data)]
    if token:
        cmd += ["-H", "Authorization: Bearer " + token]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    txt = out.stdout
    code = txt.rsplit("HTTP_CODE:", 1)[-1].strip() if "HTTP_CODE:" in txt else "?"
    body = txt.rsplit("HTTP_CODE:", 1)[0].strip()
    if raw:
        return (int(code) if code.isdigit() else 0), body
    try:
        return (int(code) if code.isdigit() else 0), json.loads(body) if body else {}
    except Exception:
        return (int(code) if code.isdigit() else 0), {"_raw": body[:500]}


def load_keypair():
    from eth_account import Account
    pk = os.environ.get("AGENT_PRIVATE_KEY", "").strip()
    if not pk:
        key_file = os.path.expanduser(
            os.environ.get("AGENT_KEY_FILE", "~/.pg/agent.key"))
        with open(key_file) as f:
            pk = f.read().strip()
    acct = Account.from_key(pk)
    return acct.address, acct


def authenticate(address, acct):
    from eth_account.messages import encode_defunct
    code, chal = curl_json("GET", f"/api/auth/challenge?address={address}")
    if code != 200 or "challenge" not in chal:
        raise SystemExit(f"challenge failed: HTTP {code} {str(chal)[:300]}")
    log(f"challenge received ({len(chal['challenge'])} chars)")
    sig = "0x" + acct.sign_message(
        encode_defunct(text=chal["challenge"])).signature.hex()
    code, ver = curl_json("POST", "/api/auth/verify",
                          {"address": address, "signature": sig})
    if code != 200 or not ver.get("token"):
        raise SystemExit(f"verify failed: HTTP {code} {str(ver)[:300]}")
    log(f"authenticated as {ver.get('address', address)}; session token received")
    return ver["token"]


def list_open_bounties():
    code, data = curl_json("GET", "/api/bounties?status=open")
    if code != 200:
        raise SystemExit(f"list bounties failed: HTTP {code}")
    return data if isinstance(data, list) else data.get("bounties", [])


def enter(token, slug, handle):
    return curl_json("POST", f"/api/bounties/{slug}/enter",
                     {"handle": handle}, token=token)


def submit(token, slug, payload):
    return curl_json("POST", f"/api/bounties/{slug}/submit",
                     payload, token=token)


def me(token):
    return curl_json("GET", "/api/me", token=token)
