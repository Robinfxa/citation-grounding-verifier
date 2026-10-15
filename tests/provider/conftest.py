from __future__ import annotations

import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa


@pytest.fixture(scope="session")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def oidc(signing_key):
    def issue(expected_nonce, client_id="oaiapp_test", **overrides):
        claims = {
            "iss": "https://auth.openai.com",
            "aud": client_id,
            "sub": "synthetic-account",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
            "nonce": expected_nonce,
        }
        claims.update(overrides)
        return jwt.encode(claims, signing_key, algorithm="RS256", headers={"kid": "local-test"})

    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key()))
    jwk.update(kid="local-test", use="sig", alg="RS256")
    return issue, {"keys": [jwk]}


@pytest.fixture
async def credentials(tmp_path):
    from grounding.codex_auth import ISSUER, REQUESTED_SCOPES, Credential, CredentialStore

    store = CredentialStore(auth_dir=tmp_path / "credentials")
    async with store.lock():
        host_id = store.host_id()
        store.save(
            Credential(
                issuer=ISSUER,
                subject="synthetic-account",
                client_id="oaiapp_test",
                ext_agent_host_id=host_id,
                id_token="synthetic-retained-id",
                access_token="synthetic-access",
                refresh_token="synthetic-refresh",
                scopes=tuple(REQUESTED_SCOPES.split()),
                expires_at=time.time() + 3600,
                saved_at=time.time(),
            )
        )
    return store
