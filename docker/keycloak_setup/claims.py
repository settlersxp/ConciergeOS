#!/usr/bin/env python3
"""Protocol mapper configuration for Keycloak setup.

Handles configuring role claims in access tokens.
"""

from keycloak_common import kc_request

from .config import REALMS


# ------------------------------------------------------------------
# Role Claim Configuration
# ------------------------------------------------------------------


def configure_role_claim(token: str, realm: str, client_uuid: str) -> None:
    """Ensure realm roles are included in the access token.

    Roles are included in the access token by default in Keycloak, but we
    verify a mapper exists to ensure the claim is always emitted.
    """
    print(f"  Configuring role claim for {realm}...")

    # Get existing protocol mappers
    resp = kc_request(
        "GET",
        f"/admin/realms/{realm}/clients/{client_uuid}/protocol-mappers/models",
        token,
    )
    resp.raise_for_status()
    mappers = resp.json()
    has_role_mapper = any(
        m["protocolMapper"] == "oidc-usermodel-realm-role-mapper"
        for m in mappers
    )

    if has_role_mapper:
        print("    ⏭ Realm role mapper already exists")
        return

    resp = kc_request(
        "POST",
        f"/admin/realms/{realm}/clients/{client_uuid}/protocol-mappers/models",
        token,
        {
            "name": "realm-roles",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-usermodel-realm-role-mapper",
            "config": {
                "access.token.claim": "true",
                "userinfo.token.claim": "true",
                "id.token.claim": "false",
                "claim.name": "realm_access.roles",
                "jsonType.label": "String",
                "multivalued": "true",
            },
        },
    )
    resp.raise_for_status()
    print("    ✓ Realm role mapper created")


def configure_all_role_claims(
    token: str,
    client_uuids: dict[str, str],
) -> None:
    """Configure role claim for all realms."""
    print("[7/8] Configuring role claim in access token...")

    for realm in REALMS:
        configure_role_claim(token, realm, client_uuids[realm])
    print()