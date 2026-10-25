"""Issue a short-lived token for a trusted internal HTTP client."""

import argparse
import time

import jwt

from app.core.settings import settings
from app.security import SCOPES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", required=True)
    parser.add_argument(
        "--scopes", nargs="+", choices=SCOPES, default=["chat", "repo:read", "net:read"]
    )
    parser.add_argument("--ttl", type=int, default=3600)
    args = parser.parse_args()
    secret = settings.jwt_secret.get_secret_value() if settings.jwt_secret else ""
    if len(secret) < 32 or settings.jwt_jwks_uri:
        parser.error(
            "Configure a local ROUTER_JWT_SECRET >=32 chars; use your "
            "identity provider for JWKS mode"
        )
    if not 60 <= args.ttl <= 3600:
        parser.error("ttl must be 60..3600 seconds")
    now = int(time.time())
    print(
        jwt.encode(
            {
                "sub": args.subject,
                "client_id": args.subject,
                "iss": settings.jwt_issuer,
                "aud": settings.jwt_audience,
                "iat": now,
                "exp": now + args.ttl,
                "scope": " ".join(args.scopes),
            },
            secret,
            algorithm="HS256",
        )
    )


if __name__ == "__main__":
    main()
