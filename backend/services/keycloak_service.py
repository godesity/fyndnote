"""Keycloak SSO support (MinIO-style OpenID Connect).

The backend validates Keycloak-issued JWTs statelessly against the realm's
JWKS endpoint (public keys fetched once and cached). No per-request calls to
Keycloak are needed once keys are cached.

Flows supported:
  - Authorization Code (frontend redirect): GET /sso/login -> Keycloak
    authorize; GET /sso/callback?code=... exchanges the code for a JWT.
  - Stateless validation: decode_token() verifies signature/audience/issuer/
    expiry from cached JWKS keys.
"""

import json
import logging
import time
from urllib.parse import urlencode

import requests

from config import (
    KEYCLOAK_CLIENT_ID,
    KEYCLOAK_CLIENT_SECRET,
    KEYCLOAK_REALM,
    KEYCLOAK_URL,
    SSO_AUDIENCE,
    SSO_ENABLED,
    SSO_REDIRECT_URI,
)

logger = logging.getLogger(__name__)

# Realm-level endpoints are derived from the base URL + realm.
_WELL_KNOWN = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/.well-known/openid-configuration"

# Token endpoint used for code exchange.
_token_endpoint = (
    f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
)
_authorize_endpoint = (
    f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth"
)
_logout_endpoint = (
    f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/logout"
)

# JWKS cache: {kid -> {"kty":..., "e":..., "n":...}} plus the fetched timestamp.
_jwks = {}
_jwks_fetched_at = 0.0
_JWKS_TTL = 300.0  # re-fetch keys every 5 minutes


def enabled():
    return SSO_ENABLED


def authorize_url(state: str) -> str:
    """Build the Keycloak authorize URL for the Authorization Code flow."""
    params = {
        "client_id": KEYCLOAK_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SSO_REDIRECT_URI + "/callback",
        "scope": "openid",
        "state": state,
    }
    return f"{_authorize_endpoint}?{urlencode(params)}"


def logout_url(id_token: str, redirect_uri: str) -> str:
    params = {
        "id_token_hint": id_token,
        "post_logout_redirect_uri": redirect_uri,
    }
    return f"{_logout_endpoint}?{urlencode(params)}"


# ---------------------------------------------------------------------------
# JWKS / JWT validation
# ---------------------------------------------------------------------------


def _b64url_decode(data: str) -> bytes:
    import base64

    rem = len(data) % 4
    if rem:
        data += "=" * (4 - rem)
    return base64.urlsafe_b64decode(data)


def _b64url_int(data: str) -> int:
    return int.from_bytes(_b64url_decode(data), "big")


def _fetch_jwks():
    """Fetch and cache the realm JWKS. Returns dict of {kid: key}."""
    global _jwks, _jwks_fetched_at
    now = time.time()
    if _jwks and (now - _jwks_fetched_at) < _JWKS_TTL:
        return _jwks
    try:
        r = requests.get(_WELL_KNOWN, timeout=10)
        r.raise_for_status()
        meta = r.json()
        jwks_url = meta["jwks_uri"]
        j = requests.get(jwks_url, timeout=10).json()
        keys = {}
        for k in j.get("keys", []):
            keys[k["kid"]] = k
        _jwks = keys
        _jwks_fetched_at = now
        logger.info("Fetched %d JWKS keys from %s", len(keys), jwks_url)
    except Exception as e:  # noqa: BLE001
        logger.warning("JWKS fetch failed: %s", e)
        # Keep stale keys so validation can still work if Keycloak is briefly down.
    return _jwks


def _decode_b64(data: str) -> dict:
    try:
        return json.loads(_b64url_decode(data).decode("utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _rsa_verify(header_b64, payload_b64, sig_b64, key):
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa

    header = _decode_b64(header_b64)

    n = _b64url_int(key["n"])
    e = _b64url_int(key["e"])

    public_numbers = rsa.RSAPublicNumbers(e=e, n=n)
    public_key = public_numbers.public_key()

    alg = header.get("alg")
    if alg == "RS256":
        h = hashes.SHA256()
        padding_ = padding.PKCS1v15()
    elif alg == "RS384":
        h = hashes.SHA384()
        padding_ = padding.PKCS1v15()
    elif alg == "RS512":
        h = hashes.SHA512()
        padding_ = padding.PKCS1v15()
    else:
        return False

    message = (header_b64 + "." + payload_b64).encode("utf-8")
    try:
        public_key.verify(_b64url_decode(sig_b64), message, padding_, h)
        return True
    except InvalidSignature:
        return False


def decode_token(token: str) -> dict | None:
    """Validate a Keycloak JWT statelessly. Returns claims dict or None."""

    parts = token.split(".")
    if len(parts) != 3:
        return None
    header_b64, payload_b64, sig_b64 = parts
    header = _decode_b64(header_b64)
    claims = _decode_b64(payload_b64)

    # Issuer must match our realm.
    expected_iss = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}"
    if claims.get("iss") != expected_iss:
        logger.warning("JWT issuer mismatch: %s", claims.get("iss"))
        return None

    # Audience check.
    aud = claims.get("aud")
    if isinstance(aud, str):
        aud = [aud]
    if SSO_AUDIENCE and SSO_AUDIENCE not in (aud or []):
        logger.warning("JWT audience mismatch: %s", aud)
        return None

    # Expiry.
    exp = claims.get("exp", 0)
    if time.time() > exp:
        logger.warning("JWT expired")
        return None

    # Signature check against cached JWKS.
    kid = header.get("kid")
    keys = _fetch_jwks()
    key = keys.get(kid)
    if key is None:
        # Force a fresh fetch once in case the key rotated.
        _jwks.clear()
        _jwks_fetched_at = 0.0
        keys = _fetch_jwks()
        key = keys.get(kid)
    if key is None:
        logger.warning("No JWKS key for kid %s", kid)
        return None

    if not _rsa_verify(header_b64, payload_b64, sig_b64, key):
        logger.warning("JWT signature invalid")
        return None

    return claims


# ---------------------------------------------------------------------------
# Token exchange (Authorization Code -> JWT)
# ---------------------------------------------------------------------------


def exchange_code(code: str) -> dict | None:
    """Exchange an auth code for Keycloak tokens. Returns tokens dict or None."""
    data = {
        "grant_type": "authorization_code",
        "client_id": KEYCLOAK_CLIENT_ID,
        "client_secret": KEYCLOAK_CLIENT_SECRET,
        "code": code,
        "redirect_uri": SSO_REDIRECT_URI + "/callback",
    }
    try:
        r = requests.post(_token_endpoint, data=data, timeout=10)
        if r.status_code != 200:
            logger.warning("Token exchange failed: %s %s", r.status_code, r.text[:200])
            return None
        return r.json()
    except Exception as e:  # noqa: BLE001
        logger.warning("Token exchange error: %s", e)
        return None


def roles_from_claims(claims: dict) -> list[str]:
    """Extract realm roles from the JWT claims (realm_access.realm-role list)."""
    realm_access = claims.get("realm_access") or {}
    roles = realm_access.get("roles") or []
    return list(roles)


def user_identity(claims: dict) -> dict:
    """Map a validated JWT's claims onto our user model."""
    roles = roles_from_claims(claims)
    # Map Keycloak realm roles onto our global_role. Prefer explicit SSO role.
    if "system_admin" in roles:
        global_role = "system_admin"
    elif "annotator" in roles:
        global_role = "annotator"
    else:
        global_role = "annotator"  # default to least privilege
    return {
        "sub": claims.get("sub") or claims.get("preferred_username"),
        "preferred_username": claims.get("preferred_username"),
        "name": claims.get("name") or claims.get("preferred_username") or "SSO user",
        "global_role": global_role,
        "roles": roles,
    }
