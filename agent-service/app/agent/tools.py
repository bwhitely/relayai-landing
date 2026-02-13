import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Awaitable

from app.models.tenant import AccountingType, CalendarType, CRMType, Tenant

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    schema: dict
    handler: Callable[[dict, Tenant], Awaitable[dict]]


TOOL_REGISTRY: dict[str, ToolDefinition] = {}


def register_tool(
    name: str,
    description: str,
    input_schema: dict,
    handler: Callable[[dict, Tenant], Awaitable[dict]],
) -> None:
    TOOL_REGISTRY[name] = ToolDefinition(
        schema={
            "name": name,
            "description": description,
            "input_schema": input_schema,
        },
        handler=handler,
    )


def get_tools_for_tenant(tenant: Tenant) -> list[dict]:
    """Return tool schemas enabled for this tenant."""
    if tenant.tools_config and "enabled" in tenant.tools_config:
        enabled = tenant.tools_config["enabled"]
        return [
            TOOL_REGISTRY[name].schema
            for name in enabled
            if name in TOOL_REGISTRY
        ]
    return [tool.schema for tool in TOOL_REGISTRY.values()]


async def execute_tool(
    tool_name: str,
    tool_input: dict,
    tenant: Tenant,
) -> str:
    definition = TOOL_REGISTRY.get(tool_name)
    if not definition:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    try:
        result = await definition.handler(tool_input, tenant)
        return json.dumps(result)
    except Exception as e:
        logger.error("Tool execution failed: %s", tool_name, exc_info=True)
        return json.dumps({"error": "Tool execution failed", "detail": str(e)})


# --- Built-in tools ---

async def _echo_handler(tool_input: dict, tenant: Tenant) -> dict:
    return {"echoed": tool_input.get("message", "")}


register_tool(
    name="echo",
    description="Echo back the input message. Useful for testing.",
    input_schema={
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "The message to echo back"},
        },
        "required": ["message"],
    },
    handler=_echo_handler,
)


async def _escalate_to_human_handler(tool_input: dict, tenant: Tenant) -> dict:
    reason = tool_input.get("reason", "No reason provided")
    summary = tool_input.get("conversation_summary", "")
    sender_id = tool_input.get("sender_id", "unknown")
    logger.info(
        "Escalation requested for tenant=%s reason=%s",
        tenant.name,
        reason,
    )

    notified_channels: list[str] = []
    errors: list[str] = []

    config = tenant.escalation_config or {}

    # Send Slack notification if configured
    slack_url = config.get("slack_webhook_url")
    if slack_url:
        try:
            from app.integrations.slack import send_escalation_notification
            await send_escalation_notification(
                webhook_url=slack_url,
                tenant_name=tenant.name,
                reason=reason,
                summary=summary,
                sender_id=sender_id,
            )
            notified_channels.append("slack")
        except Exception as e:
            logger.error("Slack escalation failed: %s", e)
            errors.append(f"slack: {e}")

    # Send email notification if configured
    email_to = config.get("email")
    if email_to:
        try:
            from app.config import get_settings
            from app.integrations.email import send_email
            settings = get_settings()
            api_key = config.get("resend_api_key") or settings.resend_api_key
            if api_key:
                html_body = (
                    f"<h2>Escalation Required</h2>"
                    f"<p><strong>Business:</strong> {tenant.name}</p>"
                    f"<p><strong>Customer:</strong> {sender_id}</p>"
                    f"<p><strong>Reason:</strong> {reason}</p>"
                )
                if summary:
                    html_body += f"<p><strong>Summary:</strong> {summary}</p>"
                await send_email(
                    api_key=api_key,
                    from_addr=settings.default_from_email,
                    to=email_to,
                    subject=f"Escalation: {tenant.name} - {reason[:50]}",
                    html_body=html_body,
                )
                notified_channels.append("email")
        except Exception as e:
            logger.error("Email escalation failed: %s", e)
            errors.append(f"email: {e}")

    result: dict = {
        "status": "escalated",
        "message": "A human team member has been notified and will follow up shortly.",
    }
    if notified_channels:
        result["notified_via"] = notified_channels
    if errors:
        result["notification_errors"] = errors

    return result


register_tool(
    name="escalate_to_human",
    description="Escalate the conversation to a human team member. Use this when you cannot resolve the customer's issue or when they explicitly request to speak to a person.",
    input_schema={
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Why the conversation is being escalated",
            },
            "conversation_summary": {
                "type": "string",
                "description": "Brief summary of the conversation so far",
            },
            "sender_id": {
                "type": "string",
                "description": "The customer's phone number or identifier",
            },
        },
        "required": ["reason"],
    },
    handler=_escalate_to_human_handler,
)


# --- CRM tools ---

def _get_crm_credentials(tenant: Tenant) -> str:
    """Decrypt and return CRM credentials for a tenant."""
    if not tenant.crm_credentials:
        raise ValueError("No CRM credentials configured for this tenant")
    from app.utils.encryption import decrypt
    return decrypt(tenant.crm_credentials)


def _get_calendar_credentials(tenant: Tenant) -> str:
    """Decrypt and return calendar credentials for a tenant."""
    if not tenant.calendar_credentials:
        raise ValueError("No calendar credentials configured for this tenant")
    from app.utils.encryption import decrypt
    return decrypt(tenant.calendar_credentials)


def _get_accounting_credentials(tenant: Tenant) -> dict:
    """Decrypt and return accounting credentials for a tenant."""
    if not tenant.accounting_credentials:
        raise ValueError("No accounting credentials configured for this tenant")
    from app.utils.encryption import decrypt
    return json.loads(decrypt(tenant.accounting_credentials))


async def _create_lead_handler(tool_input: dict, tenant: Tenant) -> dict:
    """Create a lead/contact in the tenant's CRM."""
    if tenant.crm_type == CRMType.hubspot:
        from app.integrations.hubspot import create_contact
        api_key = _get_crm_credentials(tenant)
        properties = {
            "firstname": tool_input.get("first_name", ""),
            "lastname": tool_input.get("last_name", ""),
            "email": tool_input.get("email", ""),
            "phone": tool_input.get("phone", ""),
            "company": tool_input.get("company", ""),
            "hs_lead_status": tool_input.get("lead_status", "NEW"),
        }
        notes = tool_input.get("notes", "")
        if notes:
            properties["notes"] = notes
        # Remove empty values (but keep hs_lead_status)
        properties = {k: v for k, v in properties.items() if v}
        return await create_contact(properties, api_key)

    elif tenant.crm_type == CRMType.google_sheets:
        from app.integrations.google_sheets import append_row
        creds = json.loads(_get_crm_credentials(tenant))
        sheet_id = creds.pop("sheet_id", "")
        if not sheet_id:
            return {"error": "No sheet_id in Google Sheets credentials"}
        values = [
            tool_input.get("first_name", ""),
            tool_input.get("last_name", ""),
            tool_input.get("email", ""),
            tool_input.get("phone", ""),
            tool_input.get("company", ""),
            tool_input.get("notes", ""),
        ]
        return await append_row(sheet_id, values, creds)

    elif tenant.crm_type == CRMType.splose:
        from app.integrations.splose import create_patient
        creds = json.loads(_get_crm_credentials(tenant))
        properties = {
            "firstname": tool_input.get("first_name", ""),
            "lastname": tool_input.get("last_name", ""),
            "email": tool_input.get("email", ""),
            "phone": tool_input.get("phone", ""),
        }
        properties = {k: v for k, v in properties.items() if v}
        return await create_patient(properties, creds["api_key"])

    return {"error": f"CRM type '{tenant.crm_type}' is not configured for lead creation"}


register_tool(
    name="create_lead",
    description="Create a new lead or contact in the CRM. Use this when a customer provides their contact details and you want to save them for follow-up.",
    input_schema={
        "type": "object",
        "properties": {
            "first_name": {
                "type": "string",
                "description": "Customer's first name",
            },
            "last_name": {
                "type": "string",
                "description": "Customer's last name",
            },
            "email": {
                "type": "string",
                "description": "Customer's email address",
            },
            "phone": {
                "type": "string",
                "description": "Customer's phone number",
            },
            "company": {
                "type": "string",
                "description": "Customer's company or business name",
            },
            "notes": {
                "type": "string",
                "description": "Any additional notes about the customer or their enquiry",
            },
            "lead_status": {
                "type": "string",
                "description": "The lead status based on the conversation. Use NEW for first-time enquiries, OPEN for engaged leads actively discussing services, IN_PROGRESS for leads mid-booking or awaiting follow-up, ATTEMPTED_TO_CONTACT if the customer was unresponsive, UNQUALIFIED if the customer is not a fit.",
                "enum": ["NEW", "OPEN", "IN_PROGRESS", "ATTEMPTED_TO_CONTACT", "UNQUALIFIED"],
            },
        },
        "required": ["first_name"],
    },
    handler=_create_lead_handler,
)


async def _update_lead_handler(tool_input: dict, tenant: Tenant) -> dict:
    """Update an existing lead/contact in the tenant's CRM."""
    contact_id = tool_input.get("contact_id", "")
    if not contact_id:
        return {"error": "contact_id is required"}

    if tenant.crm_type == CRMType.hubspot:
        from app.integrations.hubspot import update_contact
        api_key = _get_crm_credentials(tenant)
        properties = {}
        for field_map in [
            ("first_name", "firstname"),
            ("last_name", "lastname"),
            ("email", "email"),
            ("phone", "phone"),
            ("company", "company"),
        ]:
            val = tool_input.get(field_map[0])
            if val:
                properties[field_map[1]] = val
        if not properties:
            return {"error": "No fields to update"}
        return await update_contact(contact_id, properties, api_key)

    elif tenant.crm_type == CRMType.splose:
        from app.integrations.splose import update_patient
        creds = json.loads(_get_crm_credentials(tenant))
        updates = {}
        for field_map in [
            ("first_name", "firstname"),
            ("last_name", "lastname"),
            ("email", "email"),
            ("phone", "phone"),
        ]:
            val = tool_input.get(field_map[0])
            if val:
                if field_map[1] == "phone":
                    updates["phoneNumbers"] = [
                        {"type": "Mobile", "code": "+61", "phoneNumber": val}
                    ]
                else:
                    updates[field_map[1]] = val
        if not updates:
            return {"error": "No fields to update"}
        return await update_patient(int(contact_id), updates, creds["api_key"])

    elif tenant.crm_type == CRMType.google_sheets:
        return {"error": "Google Sheets CRM does not support updating existing rows. Create a new lead instead."}

    return {"error": f"CRM type '{tenant.crm_type}' is not configured for lead updates"}


register_tool(
    name="update_lead",
    description="Update an existing lead or contact in the CRM. Use this when you have new information about an existing customer (e.g. updated email, phone number, or name). Requires the contact_id from a previous search_contacts result.",
    input_schema={
        "type": "object",
        "properties": {
            "contact_id": {
                "type": "string",
                "description": "The CRM contact/patient ID to update (from search_contacts results)",
            },
            "first_name": {
                "type": "string",
                "description": "Updated first name",
            },
            "last_name": {
                "type": "string",
                "description": "Updated last name",
            },
            "email": {
                "type": "string",
                "description": "Updated email address",
            },
            "phone": {
                "type": "string",
                "description": "Updated phone number",
            },
            "company": {
                "type": "string",
                "description": "Updated company or business name",
            },
        },
        "required": ["contact_id"],
    },
    handler=_update_lead_handler,
)


async def _search_contacts_handler(tool_input: dict, tenant: Tenant) -> dict:
    """Search for existing contacts in the tenant's CRM."""
    query = tool_input.get("query", "")
    if not query:
        return {"error": "No search query provided"}

    if tenant.crm_type == CRMType.hubspot:
        from app.integrations.hubspot import search_contacts
        api_key = _get_crm_credentials(tenant)
        results = await search_contacts(query, api_key)
        return {"results": results, "count": len(results)}

    elif tenant.crm_type == CRMType.google_sheets:
        from app.integrations.google_sheets import read_rows
        creds = json.loads(_get_crm_credentials(tenant))
        sheet_id = creds.pop("sheet_id", "")
        if not sheet_id:
            return {"error": "No sheet_id in Google Sheets credentials"}
        rows = await read_rows(sheet_id, creds)
        # Simple text search across all cells
        matching = [
            row for row in rows
            if any(query.lower() in cell.lower() for cell in row)
        ]
        return {"results": matching, "count": len(matching)}

    elif tenant.crm_type == CRMType.splose:
        from app.integrations.splose import search_patients
        creds = json.loads(_get_crm_credentials(tenant))
        results = await search_patients(query, creds["api_key"])
        return {"results": results, "count": len(results)}

    return {"error": f"CRM type '{tenant.crm_type}' is not configured for contact search"}


register_tool(
    name="search_contacts",
    description="Search for an existing contact in the CRM by phone number or email. Use this to check if a customer is already known before creating a new lead.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The phone number or email address to search for",
            },
        },
        "required": ["query"],
    },
    handler=_search_contacts_handler,
)


# --- Availability tools ---

async def _check_availability_handler(tool_input: dict, tenant: Tenant) -> dict:
    """Check availability. Supports Google Calendar, Calendly, and Splose."""
    start_date = tool_input.get("start_date", "")
    end_date = tool_input.get("end_date", "")
    if not start_date or not end_date:
        return {"error": "Both start_date and end_date are required"}

    # Check calendar_type first
    if tenant.calendar_type == CalendarType.google_calendar:
        from app.integrations.google_calendar import check_availability as gcal_check

        creds = json.loads(_get_calendar_credentials(tenant))
        calendar_id = creds.get("calendar_id", "primary")
        busy = await gcal_check(
            calendar_id=calendar_id,
            start=start_date,
            end=end_date,
            creds_dict=creds,
        )
        return {"busy_periods": busy, "count": len(busy)}

    if tenant.calendar_type == CalendarType.calendly:
        from app.integrations.calendly import get_available_times

        creds = json.loads(_get_calendar_credentials(tenant))
        event_type_uri = creds.get("event_type_uri", "")
        if not event_type_uri:
            return {"error": "No event_type_uri in Calendly credentials"}
        slots = await get_available_times(
            event_type_uri=event_type_uri,
            start_time=start_date,
            end_time=end_date,
            api_key=creds["api_key"],
        )
        return {"slots": slots, "count": len(slots)}

    # Fall back to CRM-based availability (Splose)
    if tenant.crm_type == CRMType.splose:
        from app.integrations.splose import check_availability

        creds = json.loads(_get_crm_credentials(tenant))
        practitioner_id = tool_input.get("practitioner_id") or creds.get("default_practitioner_id")
        if not practitioner_id:
            return {"error": "No practitioner_id provided and no default configured"}

        slots = await check_availability(
            practitioner_id=int(practitioner_id),
            start_date=start_date,
            end_date=end_date,
            api_key=creds["api_key"],
            location_id=creds.get("default_location_id"),
        )
        return {"slots": slots, "count": len(slots)}

    return {"error": "No calendar or scheduling integration configured for this tenant"}


register_tool(
    name="check_availability",
    description="Check a practitioner's available appointment slots for a given date range. Use this when a customer asks about available times for booking.",
    input_schema={
        "type": "object",
        "properties": {
            "start_date": {
                "type": "string",
                "description": "Start of the date range in ISO format (e.g. 2024-01-15T00:00:00.000Z)",
            },
            "end_date": {
                "type": "string",
                "description": "End of the date range in ISO format (e.g. 2024-01-22T00:00:00.000Z). Max 100 days from start.",
            },
            "practitioner_id": {
                "type": "integer",
                "description": "The practitioner's ID. If not provided, uses the default practitioner for this business.",
            },
        },
        "required": ["start_date", "end_date"],
    },
    handler=_check_availability_handler,
)


# --- Booking tools ---

async def _book_appointment_handler(tool_input: dict, tenant: Tenant) -> dict:
    """Book an appointment. Supports Google Calendar, Calendly, and Splose."""
    start = tool_input.get("start", "")
    end = tool_input.get("end", "")
    if not start or not end:
        return {"error": "Both start and end times are required"}

    summary = tool_input.get("summary", "Appointment")

    # Check calendar_type first
    if tenant.calendar_type == CalendarType.google_calendar:
        from app.integrations.google_calendar import create_event

        creds = json.loads(_get_calendar_credentials(tenant))
        calendar_id = creds.get("calendar_id", "primary")
        result = await create_event(
            calendar_id=calendar_id,
            summary=summary,
            start=start,
            end=end,
            creds_dict=creds,
            description=tool_input.get("description"),
        )
        return result

    if tenant.calendar_type == CalendarType.calendly:
        from app.integrations.calendly import get_scheduling_link

        creds = json.loads(_get_calendar_credentials(tenant))
        event_type_uri = creds.get("event_type_uri", "")
        if not event_type_uri:
            return {"error": "No event_type_uri in Calendly credentials"}
        link_info = await get_scheduling_link(
            event_type_uri=event_type_uri,
            api_key=creds["api_key"],
        )
        return {
            "status": "scheduling_link",
            "message": "Calendly does not support direct booking via API. Please share this link with the customer.",
            "scheduling_url": link_info["scheduling_url"],
            "event_name": link_info["name"],
            "duration_minutes": link_info["duration_minutes"],
        }

    # Fall back to CRM-based booking (Splose)
    if tenant.crm_type == CRMType.splose:
        from app.integrations.splose import create_appointment

        creds = json.loads(_get_crm_credentials(tenant))
        patient_id = tool_input.get("patient_id")
        if not patient_id:
            return {"error": "patient_id is required for Splose bookings"}

        practitioner_id = tool_input.get("practitioner_id") or creds.get("default_practitioner_id")
        service_id = tool_input.get("service_id") or creds.get("default_service_id")
        location_id = tool_input.get("location_id") or creds.get("default_location_id")

        if not all([practitioner_id, service_id, location_id]):
            return {"error": "practitioner_id, service_id, and location_id are required (or must be configured as defaults)"}

        result = await create_appointment(
            start=start,
            end=end,
            patient_id=int(patient_id),
            practitioner_id=int(practitioner_id),
            service_id=int(service_id),
            location_id=int(location_id),
            api_key=creds["api_key"],
            note=tool_input.get("description"),
        )
        return result

    return {"error": "No calendar or booking integration configured for this tenant"}


register_tool(
    name="book_appointment",
    description="Book an appointment on the calendar. Use this after checking availability and confirming a time with the customer.",
    input_schema={
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Title for the appointment (e.g. customer name + service type)",
            },
            "start": {
                "type": "string",
                "description": "Appointment start time in ISO format (e.g. 2024-01-15T09:00:00+10:30)",
            },
            "end": {
                "type": "string",
                "description": "Appointment end time in ISO format (e.g. 2024-01-15T10:00:00+10:30)",
            },
            "description": {
                "type": "string",
                "description": "Optional notes or description for the appointment",
            },
            "patient_id": {
                "type": "integer",
                "description": "Patient/contact ID (required for Splose bookings, from search_contacts results)",
            },
            "practitioner_id": {
                "type": "integer",
                "description": "Practitioner ID (uses default if not provided)",
            },
            "service_id": {
                "type": "integer",
                "description": "Service ID (uses default if not provided)",
            },
            "location_id": {
                "type": "integer",
                "description": "Location ID (uses default if not provided)",
            },
        },
        "required": ["summary", "start", "end"],
    },
    handler=_book_appointment_handler,
)


# --- Email tool ---

async def _send_email_handler(tool_input: dict, tenant: Tenant) -> dict:
    """Send an email to a customer."""
    to_email = tool_input.get("to_email", "")
    subject = tool_input.get("subject", "")
    body = tool_input.get("body", "")

    if not to_email or not subject or not body:
        return {"error": "to_email, subject, and body are all required"}

    from app.config import get_settings
    from app.integrations.email import send_email

    settings = get_settings()
    # Per-tenant override via escalation_config, or shared key
    config = tenant.escalation_config or {}
    api_key = config.get("resend_api_key") or settings.resend_api_key
    if not api_key:
        return {"error": "No Resend API key configured"}

    from_addr = config.get("from_email") or settings.default_from_email
    return await send_email(
        api_key=api_key,
        from_addr=from_addr,
        to=to_email,
        subject=subject,
        html_body=body,
    )


register_tool(
    name="send_email",
    description="Send an email to a customer. Use this for appointment confirmations, follow-ups, or other email communications.",
    input_schema={
        "type": "object",
        "properties": {
            "to_email": {
                "type": "string",
                "description": "Recipient's email address",
            },
            "subject": {
                "type": "string",
                "description": "Email subject line",
            },
            "body": {
                "type": "string",
                "description": "Email body content (HTML supported)",
            },
        },
        "required": ["to_email", "subject", "body"],
    },
    handler=_send_email_handler,
)


# --- Accounting tools ---

async def _search_invoices_handler(tool_input: dict, tenant: Tenant) -> dict:
    """Search invoices in the tenant's accounting system."""
    if tenant.accounting_type != AccountingType.xero:
        return {"error": f"Accounting type '{tenant.accounting_type}' is not configured for invoice search"}

    from app.integrations.xero import search_invoices

    creds = _get_accounting_credentials(tenant)
    invoices, updated_creds = await search_invoices(
        creds=creds,
        contact_name=tool_input.get("contact_name"),
        status=tool_input.get("status"),
        invoice_number=tool_input.get("invoice_number"),
    )

    if updated_creds:
        from app.utils.encryption import encrypt
        tenant.accounting_credentials = encrypt(json.dumps(updated_creds))

    return {"invoices": invoices, "count": len(invoices)}


register_tool(
    name="search_invoices",
    description="Search for invoices in the accounting system. Use this when a customer asks about their invoices, billing, or payment history.",
    input_schema={
        "type": "object",
        "properties": {
            "contact_name": {
                "type": "string",
                "description": "Customer or contact name to filter invoices by",
            },
            "status": {
                "type": "string",
                "description": "Invoice status filter",
                "enum": ["DRAFT", "SUBMITTED", "AUTHORISED", "PAID", "VOIDED"],
            },
            "invoice_number": {
                "type": "string",
                "description": "Specific invoice number to search for",
            },
        },
    },
    handler=_search_invoices_handler,
)


async def _check_payment_status_handler(tool_input: dict, tenant: Tenant) -> dict:
    """Check payment status for a specific invoice."""
    invoice_id = tool_input.get("invoice_id", "")
    if not invoice_id:
        return {"error": "invoice_id is required"}

    if tenant.accounting_type != AccountingType.xero:
        return {"error": f"Accounting type '{tenant.accounting_type}' is not configured for payment status checks"}

    from app.integrations.xero import get_invoice

    creds = _get_accounting_credentials(tenant)
    invoice, updated_creds = await get_invoice(creds=creds, invoice_id=invoice_id)

    if updated_creds:
        from app.utils.encryption import encrypt
        tenant.accounting_credentials = encrypt(json.dumps(updated_creds))

    return invoice


register_tool(
    name="check_payment_status",
    description="Check the payment status and details of a specific invoice. Use this when a customer asks about a particular invoice's payment status.",
    input_schema={
        "type": "object",
        "properties": {
            "invoice_id": {
                "type": "string",
                "description": "The invoice ID (from search_invoices results)",
            },
        },
        "required": ["invoice_id"],
    },
    handler=_check_payment_status_handler,
)
