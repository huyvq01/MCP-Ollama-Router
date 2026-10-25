"""Transport authentication and per-identity operation ownership."""

from __future__ import annotations

import hashlib
import time
from urllib.parse import urlsplit

from fastmcp.server.auth import RemoteAuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.dependencies import get_access_token
from pydantic import AnyHttpUrl

SCOPES = [
    "chat",
    "repo:read",
    "repo:write",
    "repo:run",
    "net:read",
    "git:write",
    "git:network",
    "repo:publish",
    "admin",
]


def identity() -> str:
    token = get_access_token()
    if token is None:
        return "local-stdio"
    value = token.subject or token.client_id
    if not value:
        raise PermissionError("Token needs a subject or client_id")
    return hashlib.sha256(value.encode()).hexdigest()


def session_key(session_id: str) -> str:
    owner = identity()
    if owner != "local-stdio" and len(session_id) > 95:
        raise ValueError("HTTP session_id must be <=95 characters")
    return session_id if owner == "local-stdio" else owner[:32] + ":" + session_id


class ExpiringJWTVerifier(JWTVerifier):
    async def verify_token(self, token):
        access = await super().verify_token(token)
        if (
            access is None
            or access.expires_at is None
            or access.expires_at <= time.time()
        ):
            return None
        if not (access.subject or access.client_id):
            return None
        return access


def build_auth(config):
    if config.transport == "stdio":
        return None
    if config.transport not in {"http", "streamable-http"}:
        raise ValueError("transport must be stdio or http")
    public = urlsplit(config.http_public_url)
    if (
        public.scheme not in {"http", "https"}
        or public.username
        or public.password
        or public.query
        or public.fragment
    ):
        raise ValueError("Configure a clean HTTP(S) public URL")
    if public.scheme != "https" and public.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise ValueError(
            "Remote public URLs require HTTPS; terminate TLS at a reverse proxy"
        )
    if (
        config.http_host not in {"127.0.0.1", "localhost", "::1"}
        and public.scheme != "https"
    ):
        raise ValueError(
            "Non-loopback listeners require an HTTPS public URL and TLS proxy"
        )
    if "*" in config.http_allowed_hosts or "*" in config.http_allowed_origins:
        raise ValueError("Configure exact allowed hosts/origins, not wildcards")
    if config.jwt_jwks_uri:
        if not config.jwt_jwks_uri.startswith("https://"):
            raise ValueError("JWKS endpoint requires HTTPS")
        verifier = ExpiringJWTVerifier(
            jwks_uri=config.jwt_jwks_uri,
            algorithm="RS256",
            issuer=config.jwt_issuer,
            audience=config.jwt_audience,
            required_scopes=[],
        )
    else:
        secret = config.jwt_secret.get_secret_value() if config.jwt_secret else ""
        if len(secret) < 32:
            raise ValueError(
                "HTTP requires ROUTER_JWT_SECRET of at least 32 characters, "
                "or a JWKS provider"
            )
        verifier = ExpiringJWTVerifier(
            public_key=secret,
            algorithm="HS256",
            issuer=config.jwt_issuer,
            audience=config.jwt_audience,
            required_scopes=[],
        )
    if config.authorization_servers:
        if any(not u.startswith("https://") for u in config.authorization_servers):
            raise ValueError("Authorization servers require HTTPS")
        return RemoteAuthProvider(
            token_verifier=verifier,
            authorization_servers=[AnyHttpUrl(u) for u in config.authorization_servers],
            base_url=config.http_public_url,
            scopes_supported=SCOPES,
        )
    return verifier
