import json
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.agent.tools import execute_tool
from app.integrations.xero import _ensure_valid_token, get_invoice, search_invoices
from app.models.tenant import AccountingType, CRMType, Tenant


def _make_creds(expired: bool = False) -> dict:
    if expired:
        expiry = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    else:
        expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    return {
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "refresh_token": "test-refresh-token",
        "access_token": "test-access-token",
        "token_expiry": expiry,
        "xero_tenant_id": "test-xero-tenant-id",
    }


@pytest.fixture
def xero_tenant() -> Tenant:
    return Tenant(
        id=uuid.uuid4(),
        name="Xero Business",
        crm_type=CRMType.none,
        accounting_type=AccountingType.xero,
        accounting_credentials="encrypted-xero-creds",
        max_conversations_per_month=100,
        is_active=True,
    )


class TestEnsureValidToken:
    @pytest.mark.asyncio
    async def test_valid_token_skips_refresh(self):
        creds = _make_creds(expired=False)
        token, updated = await _ensure_valid_token(creds)
        assert token == "test-access-token"
        assert updated is None

    @pytest.mark.asyncio
    async def test_expired_token_triggers_refresh(self):
        creds = _make_creds(expired=True)

        mock_response = httpx.Response(
            200,
            json={
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 1800,
            },
            request=httpx.Request("POST", "https://identity.xero.com/connect/token"),
        )

        with patch("app.integrations.xero.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            token, updated = await _ensure_valid_token(creds)

        assert token == "new-access-token"
        assert updated is not None
        assert updated["access_token"] == "new-access-token"
        assert updated["refresh_token"] == "new-refresh-token"

    @pytest.mark.asyncio
    async def test_no_expiry_triggers_refresh(self):
        creds = _make_creds(expired=False)
        creds["token_expiry"] = ""

        mock_response = httpx.Response(
            200,
            json={
                "access_token": "refreshed-token",
                "expires_in": 1800,
            },
            request=httpx.Request("POST", "https://identity.xero.com/connect/token"),
        )

        with patch("app.integrations.xero.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            token, updated = await _ensure_valid_token(creds)

        assert token == "refreshed-token"
        assert updated is not None


class TestSearchInvoices:
    @pytest.mark.asyncio
    async def test_search_by_contact_name(self):
        creds = _make_creds(expired=False)
        mock_response = httpx.Response(
            200,
            json={
                "Invoices": [
                    {
                        "InvoiceID": "inv-001",
                        "InvoiceNumber": "INV-0001",
                        "Contact": {"Name": "Test Customer"},
                        "Status": "AUTHORISED",
                        "Total": 500.00,
                        "AmountDue": 500.00,
                        "AmountPaid": 0,
                        "DateString": "2024-01-15",
                        "DueDateString": "2024-02-15",
                        "CurrencyCode": "AUD",
                    }
                ]
            },
            request=httpx.Request("GET", "https://api.xero.com/api.xro/2.0/Invoices"),
        )

        with patch("app.integrations.xero.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            invoices, updated = await search_invoices(creds, contact_name="Test Customer")

        assert len(invoices) == 1
        assert invoices[0]["invoice_number"] == "INV-0001"
        assert invoices[0]["contact_name"] == "Test Customer"
        assert updated is None  # Token was valid

    @pytest.mark.asyncio
    async def test_search_empty_results(self):
        creds = _make_creds(expired=False)
        mock_response = httpx.Response(
            200,
            json={"Invoices": []},
            request=httpx.Request("GET", "https://api.xero.com/api.xro/2.0/Invoices"),
        )

        with patch("app.integrations.xero.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            invoices, updated = await search_invoices(creds, status="PAID")

        assert invoices == []


class TestGetInvoice:
    @pytest.mark.asyncio
    async def test_get_invoice_with_line_items(self):
        creds = _make_creds(expired=False)
        mock_response = httpx.Response(
            200,
            json={
                "Invoices": [
                    {
                        "InvoiceID": "inv-001",
                        "InvoiceNumber": "INV-0001",
                        "Contact": {"Name": "Test Customer"},
                        "Status": "AUTHORISED",
                        "Total": 500.00,
                        "AmountDue": 500.00,
                        "AmountPaid": 0,
                        "DateString": "2024-01-15",
                        "DueDateString": "2024-02-15",
                        "CurrencyCode": "AUD",
                        "LineItems": [
                            {
                                "Description": "Service A",
                                "Quantity": 2,
                                "UnitAmount": 250.00,
                                "LineAmount": 500.00,
                                "AccountCode": "200",
                            }
                        ],
                        "Payments": [
                            {
                                "DateString": "2024-01-20",
                                "Amount": 250.00,
                                "Reference": "PAY-001",
                            }
                        ],
                    }
                ]
            },
            request=httpx.Request("GET", "https://api.xero.com/api.xro/2.0/Invoices/inv-001"),
        )

        with patch("app.integrations.xero.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            invoice, updated = await get_invoice(creds, "inv-001")

        assert invoice["invoice_id"] == "inv-001"
        assert len(invoice["line_items"]) == 1
        assert invoice["line_items"][0]["description"] == "Service A"
        assert len(invoice["payments"]) == 1
        assert invoice["payments"][0]["amount"] == 250.00


class TestXeroToolDispatch:
    @pytest.mark.asyncio
    async def test_search_invoices_tool(self, xero_tenant):
        creds = _make_creds(expired=False)
        mock_response = httpx.Response(
            200,
            json={
                "Invoices": [
                    {
                        "InvoiceID": "inv-001",
                        "InvoiceNumber": "INV-0001",
                        "Contact": {"Name": "Test Customer"},
                        "Status": "AUTHORISED",
                        "Total": 500.00,
                        "AmountDue": 500.00,
                        "AmountPaid": 0,
                        "DateString": "2024-01-15",
                        "DueDateString": "2024-02-15",
                        "CurrencyCode": "AUD",
                    }
                ]
            },
            request=httpx.Request("GET", "https://api.xero.com/api.xro/2.0/Invoices"),
        )

        with patch("app.integrations.xero.httpx.AsyncClient") as mock_client_cls, \
             patch("app.agent.tools._get_accounting_credentials", return_value=creds):
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result_str = await execute_tool(
                "search_invoices",
                {"contact_name": "Test Customer"},
                xero_tenant,
            )

        result = json.loads(result_str)
        assert result["count"] == 1
        assert result["invoices"][0]["invoice_number"] == "INV-0001"

    @pytest.mark.asyncio
    async def test_check_payment_status_tool(self, xero_tenant):
        creds = _make_creds(expired=False)
        mock_response = httpx.Response(
            200,
            json={
                "Invoices": [
                    {
                        "InvoiceID": "inv-001",
                        "InvoiceNumber": "INV-0001",
                        "Contact": {"Name": "Test Customer"},
                        "Status": "PAID",
                        "Total": 500.00,
                        "AmountDue": 0,
                        "AmountPaid": 500.00,
                        "DateString": "2024-01-15",
                        "DueDateString": "2024-02-15",
                        "CurrencyCode": "AUD",
                        "LineItems": [],
                        "Payments": [
                            {
                                "DateString": "2024-01-20",
                                "Amount": 500.00,
                                "Reference": "PAY-001",
                            }
                        ],
                    }
                ]
            },
            request=httpx.Request("GET", "https://api.xero.com/api.xro/2.0/Invoices/inv-001"),
        )

        with patch("app.integrations.xero.httpx.AsyncClient") as mock_client_cls, \
             patch("app.agent.tools._get_accounting_credentials", return_value=creds):
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result_str = await execute_tool(
                "check_payment_status",
                {"invoice_id": "inv-001"},
                xero_tenant,
            )

        result = json.loads(result_str)
        assert result["status"] == "PAID"
        assert result["amount_paid"] == 500.00

    @pytest.mark.asyncio
    async def test_search_invoices_no_accounting(self):
        tenant = Tenant(
            id=uuid.uuid4(),
            name="No Accounting",
            crm_type=CRMType.none,
            accounting_type=AccountingType.none,
            max_conversations_per_month=100,
            is_active=True,
        )

        result_str = await execute_tool(
            "search_invoices",
            {"contact_name": "Test"},
            tenant,
        )
        result = json.loads(result_str)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_check_payment_missing_invoice_id(self, xero_tenant):
        result_str = await execute_tool(
            "check_payment_status",
            {},
            xero_tenant,
        )
        result = json.loads(result_str)
        assert "error" in result
        assert "invoice_id" in result["error"]

    @pytest.mark.asyncio
    async def test_credential_persistence_on_refresh(self, xero_tenant):
        """When Xero token is refreshed, updated creds should be written to tenant."""
        expired_creds = _make_creds(expired=True)

        refresh_response = httpx.Response(
            200,
            json={
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 1800,
            },
            request=httpx.Request("POST", "https://identity.xero.com/connect/token"),
        )
        invoices_response = httpx.Response(
            200,
            json={"Invoices": []},
            request=httpx.Request("GET", "https://api.xero.com/api.xro/2.0/Invoices"),
        )

        with patch("app.integrations.xero.httpx.AsyncClient") as mock_client_cls, \
             patch("app.agent.tools._get_accounting_credentials", return_value=expired_creds), \
             patch("app.utils.encryption.encrypt", return_value="encrypted-updated") as mock_encrypt:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=refresh_response)
            mock_client.get = AsyncMock(return_value=invoices_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await execute_tool(
                "search_invoices",
                {"contact_name": "Test"},
                xero_tenant,
            )

        # Verify encrypt was called with the updated credentials
        mock_encrypt.assert_called_once()
        encrypted_arg = mock_encrypt.call_args[0][0]
        updated_creds = json.loads(encrypted_arg)
        assert updated_creds["access_token"] == "new-access-token"
        # Verify tenant's accounting_credentials was updated
        assert xero_tenant.accounting_credentials == "encrypted-updated"
