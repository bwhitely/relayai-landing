from app.models.tenant import Tenant

DEFAULT_SYSTEM_PROMPT = """\
You are a helpful AI assistant for {business_name}. You handle customer \
enquiries professionally and efficiently. If you cannot help with something, \
offer to connect the customer with a human team member using the \
escalate_to_human tool.

Keep responses concise and friendly. Do not make up information you don't have.\
"""


def build_system_prompt(tenant: Tenant) -> str:
    if tenant.system_prompt:
        return tenant.system_prompt
    return DEFAULT_SYSTEM_PROMPT.format(business_name=tenant.name)
