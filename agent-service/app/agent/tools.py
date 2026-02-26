import base64
import html
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
    except Exception:
        logger.error("Tool execution failed: %s", tool_name, exc_info=True)
        return json.dumps({"error": "Tool execution failed — please try again or escalate to a human"})


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
                    f"<p><strong>Business:</strong> {html.escape(tenant.name)}</p>"
                    f"<p><strong>Customer:</strong> {html.escape(sender_id)}</p>"
                    f"<p><strong>Reason:</strong> {html.escape(reason)}</p>"
                )
                if summary:
                    html_body += f"<p><strong>Summary:</strong> {html.escape(summary)}</p>"
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

    # Send SMS notification to owner if configured
    owner_sms = config.get("owner_sms")
    if owner_sms:
        try:
            from app.config import get_settings
            from app.integrations.twilio import send_sms_message
            settings = get_settings()
            from_number = settings.twilio_from_number
            if from_number:
                sms_body = (
                    f"RelayAI lead alert\n"
                    f"Business: {tenant.name}\n"
                    f"Reason: {reason}"
                )
                if summary:
                    sms_body += f"\nSummary: {summary[:120]}"
                await send_sms_message(
                    to=owner_sms,
                    body=sms_body,
                    from_number=from_number,
                )
                notified_channels.append("sms")
            else:
                logger.warning(
                    "owner_sms configured but TWILIO_FROM_NUMBER not set in environment"
                )
        except Exception as e:
            logger.error("SMS escalation failed: %s", e)
            errors.append(f"sms: {e}")

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
        # Note: 'notes' is not a default HubSpot contact property, so we skip it.
        # Notes are preserved in the conversation history.
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


# --- Appointment listing tool ---

async def _list_appointments_handler(tool_input: dict, tenant: Tenant) -> dict:
    """List upcoming appointments. Supports Google Calendar, Calendly, and Splose."""
    start_date = tool_input.get("start_date", "")
    end_date = tool_input.get("end_date", "")
    if not start_date or not end_date:
        return {"error": "Both start_date and end_date are required"}

    # Check calendar_type first
    if tenant.calendar_type == CalendarType.google_calendar:
        from app.integrations.google_calendar import list_events

        creds = json.loads(_get_calendar_credentials(tenant))
        calendar_id = creds.get("calendar_id", "primary")
        events = await list_events(
            calendar_id=calendar_id,
            time_min=start_date,
            time_max=end_date,
            creds_dict=creds,
        )
        return {"appointments": events, "count": len(events)}

    if tenant.calendar_type == CalendarType.calendly:
        from app.integrations.calendly import list_scheduled_events

        creds = json.loads(_get_calendar_credentials(tenant))
        events = await list_scheduled_events(
            api_key=creds["api_key"],
            min_start_time=start_date,
            max_start_time=end_date,
            invitee_email=tool_input.get("email"),
        )
        return {"appointments": events, "count": len(events)}

    # Fall back to CRM-based (Splose)
    if tenant.crm_type == CRMType.splose:
        from app.integrations.splose import list_appointments

        creds = json.loads(_get_crm_credentials(tenant))
        patient_id = tool_input.get("patient_id")
        practitioner_id = tool_input.get("practitioner_id") or creds.get("default_practitioner_id")
        appts = await list_appointments(
            api_key=creds["api_key"],
            patient_id=int(patient_id) if patient_id else None,
            practitioner_id=int(practitioner_id) if practitioner_id else None,
            start_date=start_date,
            end_date=end_date,
        )
        return {"appointments": appts, "count": len(appts)}

    return {"error": "No calendar or scheduling integration configured for this tenant"}


register_tool(
    name="list_appointments",
    description="List upcoming appointments in a date range. Use this when a customer asks 'when is my next appointment?' or wants to see their bookings.",
    input_schema={
        "type": "object",
        "properties": {
            "start_date": {
                "type": "string",
                "description": "Start of date range in ISO format (e.g. 2024-01-15T00:00:00.000Z)",
            },
            "end_date": {
                "type": "string",
                "description": "End of date range in ISO format (e.g. 2024-01-22T00:00:00.000Z)",
            },
            "patient_id": {
                "type": "integer",
                "description": "Patient/contact ID to filter by (for Splose)",
            },
            "email": {
                "type": "string",
                "description": "Invitee email to filter by (for Calendly)",
            },
            "practitioner_id": {
                "type": "integer",
                "description": "Practitioner ID to filter by (uses default if not provided)",
            },
        },
        "required": ["start_date", "end_date"],
    },
    handler=_list_appointments_handler,
)


# --- Appointment cancellation tool ---

async def _cancel_appointment_handler(tool_input: dict, tenant: Tenant) -> dict:
    """Cancel an appointment. Supports Google Calendar, Calendly, and Splose."""
    appointment_id = tool_input.get("appointment_id", "")
    if not appointment_id:
        return {"error": "appointment_id is required"}

    reason = tool_input.get("reason", "Cancelled by customer")

    # Check calendar_type first
    if tenant.calendar_type == CalendarType.google_calendar:
        from app.integrations.google_calendar import delete_event

        creds = json.loads(_get_calendar_credentials(tenant))
        calendar_id = creds.get("calendar_id", "primary")
        return await delete_event(
            calendar_id=calendar_id,
            event_id=appointment_id,
            creds_dict=creds,
        )

    if tenant.calendar_type == CalendarType.calendly:
        from app.integrations.calendly import cancel_event

        creds = json.loads(_get_calendar_credentials(tenant))
        return await cancel_event(
            event_uri=appointment_id,
            reason=reason,
            api_key=creds["api_key"],
        )

    # Fall back to CRM-based (Splose)
    if tenant.crm_type == CRMType.splose:
        from app.integrations.splose import cancel_appointment

        creds = json.loads(_get_crm_credentials(tenant))
        return await cancel_appointment(
            appointment_id=int(appointment_id),
            api_key=creds["api_key"],
            reason=reason,
        )

    return {"error": "No calendar or booking integration configured for this tenant"}


register_tool(
    name="cancel_appointment",
    description="Cancel an existing appointment. Use this when a customer wants to cancel a booking. Requires the appointment_id from list_appointments results.",
    input_schema={
        "type": "object",
        "properties": {
            "appointment_id": {
                "type": "string",
                "description": "The appointment/event ID to cancel (from list_appointments results)",
            },
            "reason": {
                "type": "string",
                "description": "Reason for cancellation",
            },
        },
        "required": ["appointment_id"],
    },
    handler=_cancel_appointment_handler,
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


async def _call_http_handler(tool_input: dict, tenant: Tenant) -> dict:
    """Call a pre-configured HTTP endpoint from the tenant's tools_config."""
    import httpx

    endpoint_name = tool_input.get("endpoint_name", "").strip()
    if not endpoint_name:
        return {"error": "endpoint_name is required"}

    # Load configured endpoints — admin pre-configures these, no arbitrary URLs allowed
    configured = {}
    if tenant.tools_config:
        for ep in tenant.tools_config.get("http_endpoints", []):
            if isinstance(ep, dict) and "name" in ep and "url" in ep:
                configured[ep["name"]] = ep

    endpoint = configured.get(endpoint_name)
    if not endpoint:
        available = list(configured.keys())
        return {"error": f"Unknown endpoint '{endpoint_name}'. Available: {available}"}

    url = endpoint["url"]
    method = endpoint.get("method", "GET").upper()
    headers = dict(endpoint.get("headers", {}))

    # Substitute path parameters
    for key, value in (tool_input.get("path_params") or {}).items():
        url = url.replace(f"{{{key}}}", str(value))

    query_params = tool_input.get("query_params") or {}
    body = tool_input.get("body") or None

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=query_params if query_params else None,
                json=body,
            )
            response.raise_for_status()
        try:
            return {"status": response.status_code, "data": response.json()}
        except Exception:
            return {"status": response.status_code, "data": response.text[:5000]}
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP {e.response.status_code}: {e.response.text[:500]}"}
    except httpx.RequestError as e:
        return {"error": f"Request failed: {e}"}


async def _process_document_handler(tool_input: dict, tenant: Tenant) -> dict:
    """Download a document and use Claude to extract information from it."""
    import httpx

    document_url = tool_input.get("document_url", "").strip()
    extraction_instructions = tool_input.get("extraction_instructions", "Extract all key information from this document.")

    if not document_url:
        return {"error": "document_url is required"}

    # Download the document
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(document_url)
            response.raise_for_status()
    except httpx.HTTPError as e:
        return {"error": f"Failed to download document: {e}"}

    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    raw_bytes = response.content

    # Build the content block for Claude
    if content_type == "application/pdf":
        media_type = "application/pdf"
        source_type = "base64"
        data = base64.standard_b64encode(raw_bytes).decode("utf-8")
        document_block = {
            "type": "document",
            "source": {"type": source_type, "media_type": media_type, "data": data},
        }
    elif content_type in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        data = base64.standard_b64encode(raw_bytes).decode("utf-8")
        document_block = {
            "type": "image",
            "source": {"type": "base64", "media_type": content_type, "data": data},
        }
    else:
        # Treat as plain text
        try:
            text = raw_bytes.decode("utf-8", errors="replace")
        except Exception:
            return {"error": f"Unsupported document type: {content_type}"}
        document_block = {"type": "text", "text": text[:20000]}

    from app.integrations.anthropic import get_client, get_settings
    settings = get_settings()

    llm_response = await get_client().messages.create(
        model=settings.default_model,
        max_tokens=2048,
        system="You are a document extraction assistant. Extract the requested information accurately and return it as structured JSON.",
        messages=[
            {
                "role": "user",
                "content": [
                    document_block,
                    {"type": "text", "text": extraction_instructions + "\n\nReturn your response as JSON."},
                ],
            }
        ],
    )

    extracted_text = ""
    for block in llm_response.content:
        if hasattr(block, "text"):
            extracted_text = block.text
            break
        elif isinstance(block, dict) and block.get("type") == "text":
            extracted_text = block.get("text", "")
            break

    try:
        return {"extracted_data": json.loads(extracted_text)}
    except (json.JSONDecodeError, ValueError):
        return {"extracted_data": extracted_text}


register_tool(
    name="call_http",
    description=(
        "Call a pre-configured external API endpoint. Use this to fetch or submit data "
        "to external systems set up for your business. "
        "Only pre-configured endpoints are available — ask your administrator which names to use."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "endpoint_name": {
                "type": "string",
                "description": "Name of the pre-configured endpoint to call",
            },
            "path_params": {
                "type": "object",
                "description": "URL path parameters. E.g. {\"id\": \"123\"} replaces {id} in the URL.",
                "additionalProperties": {"type": "string"},
            },
            "query_params": {
                "type": "object",
                "description": "Query string parameters to append to the URL.",
                "additionalProperties": {"type": "string"},
            },
            "body": {
                "type": "object",
                "description": "Request body for POST/PUT/PATCH requests (sent as JSON).",
            },
        },
        "required": ["endpoint_name"],
    },
    handler=_call_http_handler,
)


register_tool(
    name="process_document",
    description=(
        "Download and process a document (PDF, image, or text file) to extract information from it. "
        "Use this when a customer shares a document URL and you need to read its contents — "
        "such as an invoice, referral letter, intake form, quote, or contract."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "document_url": {
                "type": "string",
                "description": "The URL of the document to process (PDF, image, or text file)",
            },
            "extraction_instructions": {
                "type": "string",
                "description": (
                    "What information to extract from the document. "
                    "Be specific, e.g. 'Extract the invoice number, date, total amount, and line items'"
                ),
            },
        },
        "required": ["document_url", "extraction_instructions"],
    },
    handler=_process_document_handler,
)
