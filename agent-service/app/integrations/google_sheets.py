import logging
import time

import httpx

logger = logging.getLogger(__name__)

SHEETS_API_BASE = "https://sheets.googleapis.com/v4/spreadsheets"
TOKEN_URL = "https://oauth2.googleapis.com/token"


async def _get_access_token(credentials: dict) -> str:
    """Exchange service account credentials for an access token.

    credentials should contain:
        client_email, private_key, token_uri (optional)
    Uses a simplified JWT-based flow via Google's token endpoint.
    """
    import json
    import base64
    import hashlib
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    now = int(time.time())
    header = base64.urlsafe_b64encode(json.dumps(
        {"alg": "RS256", "typ": "JWT"}
    ).encode()).rstrip(b"=").decode()

    payload = base64.urlsafe_b64encode(json.dumps({
        "iss": credentials["client_email"],
        "scope": "https://www.googleapis.com/auth/spreadsheets",
        "aud": TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }).encode()).rstrip(b"=").decode()

    signing_input = f"{header}.{payload}".encode()

    private_key = serialization.load_pem_private_key(
        credentials["private_key"].encode(), password=None
    )
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()

    jwt_token = f"{header}.{payload}.{sig_b64}"

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": jwt_token,
            },
        )
        response.raise_for_status()
        return response.json()["access_token"]


async def append_row(
    sheet_id: str,
    values: list,
    credentials: dict,
    sheet_name: str = "Sheet1",
) -> dict:
    """Append a row to a Google Sheet.

    values: list of cell values, e.g. ["John", "Doe", "john@example.com", "+61400000000"]
    """
    access_token = await _get_access_token(credentials)
    range_name = f"{sheet_name}!A:Z"

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{SHEETS_API_BASE}/{sheet_id}/values/{range_name}:append",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
            json={"values": [values]},
        )
        response.raise_for_status()
        data = response.json()
        logger.info("Appended row to sheet=%s", sheet_id)
        return {
            "status": "appended",
            "updated_range": data.get("updates", {}).get("updatedRange", ""),
            "updated_rows": data.get("updates", {}).get("updatedRows", 0),
        }


async def read_rows(
    sheet_id: str,
    credentials: dict,
    sheet_name: str = "Sheet1",
    range_suffix: str = "A:Z",
) -> list[list[str]]:
    """Read all rows from a Google Sheet."""
    access_token = await _get_access_token(credentials)
    range_name = f"{sheet_name}!{range_suffix}"

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{SHEETS_API_BASE}/{sheet_id}/values/{range_name}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        data = response.json()
        return data.get("values", [])
