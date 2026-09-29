# coding=utf-8

"""
Reads the claims of the id_token of a logged in user, to show them on the account page.
"""

import base64
import json
import logging
from collections import namedtuple

logger = logging.getLogger(__name__)

IdentityClaim = namedtuple("IdentityClaim", ["label", "name", "value"])

# Protocol claims that mean nothing to a person, and claims shown elsewhere on the page
HIDDEN_CLAIMS = frozenset(
    {
        "realm_access",
        "acr",
        "exp",
        "iat",
        "auth_time",
        "jti",
        "nonce",
        "at_hash",
        "sid",
        "session_state",
        "azp",
        "typ",
        "iss",
        "aud",
        "nbf",
        "c_hash",
        "s_hash",
    }
)

# Claims shown first, in this order, with a friendly label
KNOWN_CLAIM_LABELS = {
    "name": "Name",
    "given_name": "First name",
    "family_name": "Last name",
    "preferred_username": "Username",
    "email": "Email",
    "email_verified": "Email verified",
    "sub": "Identifier",
}


def decode_jwt_payload(jwt_string):
    """
    Returns the payload of a JWT as a dictionary, without checking the signature
    (the token was verified when the user logged in). Returns an empty dictionary if it can't be read.
    """
    try:
        payload = jwt_string.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload))
    except (AttributeError, IndexError, ValueError):
        logger.warning("Could not decode the id_token of the user")
        return {}
    return decoded if isinstance(decoded, dict) else {}


def format_claim_value(value):
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, tuple)):
        return ", ".join(format_claim_value(item) for item in value)
    if isinstance(value, dict):
        return "; ".join(
            f"{key}: {format_claim_value(item)}" for key, item in value.items()
        )
    return str(value)


def extract_identity_claims(id_token_jwt):
    """
    Returns the claims of the id_token that are meaningful for a person, as a list of IdentityClaim:
    the well-known claims first, then the others sorted by name.
    """
    claims = decode_jwt_payload(id_token_jwt)
    shown = {
        name: format_claim_value(value)
        for name, value in claims.items()
        if name not in HIDDEN_CLAIMS
    }
    known_names = [name for name in KNOWN_CLAIM_LABELS if name in shown]
    other_names = sorted(name for name in shown if name not in KNOWN_CLAIM_LABELS)
    return [
        IdentityClaim(KNOWN_CLAIM_LABELS.get(name, name), name, shown[name])
        for name in known_names + other_names
    ]
