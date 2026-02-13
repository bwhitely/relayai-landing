import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Awaitable

from app.models.tenant import CRMType, Tenant

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
    logger.info(
        "Escalation requested for tenant=%s reason=%s",
        tenant.name,
        reason,
    )
    # TODO: Send notification via Slack/email using tenant.escalation_config
    return {
        "status": "escalated",
        "message": "A human team member has been notified and will follow up shortly.",
    }


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
        }
        # Remove empty values
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
    """Check practitioner availability. Currently supports Splose only."""
    if tenant.crm_type != CRMType.splose:
        return {"error": "Availability checking is only available for Splose-integrated tenants"}

    from app.integrations.splose import check_availability

    creds = json.loads(_get_crm_credentials(tenant))
    practitioner_id = tool_input.get("practitioner_id") or creds.get("default_practitioner_id")
    if not practitioner_id:
        return {"error": "No practitioner_id provided and no default configured"}

    start_date = tool_input.get("start_date", "")
    end_date = tool_input.get("end_date", "")
    if not start_date or not end_date:
        return {"error": "Both start_date and end_date are required"}

    slots = await check_availability(
        practitioner_id=int(practitioner_id),
        start_date=start_date,
        end_date=end_date,
        api_key=creds["api_key"],
        location_id=creds.get("default_location_id"),
    )
    return {"slots": slots, "count": len(slots)}


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
