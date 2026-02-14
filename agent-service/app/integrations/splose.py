import logging

import httpx

logger = logging.getLogger(__name__)

SPLOSE_API_BASE = "https://api.splose.com/v1"
USER_AGENT = "RelayAI-AgentService/1.0"


def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }


async def create_patient(
    properties: dict,
    api_key: str,
) -> dict:
    """Create a patient in Splose.

    Required fields: firstname, lastname.
    Optional: email, phoneNumbers, birthdate, city, state, postalCode, etc.
    """
    body = {
        "firstname": properties.get("firstname", ""),
        "lastname": properties.get("lastname", ""),
    }
    # Add optional fields if present
    for field in (
        "email", "birthdate", "city", "state", "postalCode", "country",
        "addressL1", "addressL2", "sex", "ndisNumber", "communicationPreference",
    ):
        if properties.get(field):
            body[field] = properties[field]

    # Handle phone numbers
    if properties.get("phone"):
        body["phoneNumbers"] = [
            {"type": "Mobile", "code": "+61", "phoneNumber": properties["phone"]}
        ]

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{SPLOSE_API_BASE}/patients",
            headers=_headers(api_key),
            json=body,
        )
        response.raise_for_status()
        data = response.json()
        logger.info("Created Splose patient id=%s", data.get("id"))
        return {
            "status": "created",
            "patient_id": data["id"],
            "firstname": data.get("firstname", ""),
            "lastname": data.get("lastname", ""),
        }


async def get_patient(patient_id: int, api_key: str) -> dict:
    """Get a single patient by ID."""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{SPLOSE_API_BASE}/patients/{patient_id}",
            headers=_headers(api_key),
        )
        response.raise_for_status()
        return response.json()


async def update_patient(patient_id: int, updates: dict, api_key: str) -> dict:
    """Update an existing patient in Splose.

    Splose PUT requires many fields, so we GET the current patient first,
    merge the updates, then PUT the full object back.
    """
    current = await get_patient(patient_id, api_key)

    # Merge updates into current data
    for key, value in updates.items():
        if value is not None:
            current[key] = value

    # Build the required PUT body from current + updates
    # Splose PUT requires all these fields
    body = {
        "firstname": current.get("firstname", ""),
        "lastname": current.get("lastname", ""),
        "email": current.get("email", ""),
        "sex": current.get("sex", ""),
        "genderIdentity": current.get("genderIdentity", ""),
        "alert": current.get("alert", ""),
        "birthdate": current.get("birthdate", ""),
        "city": current.get("city", ""),
        "state": current.get("state", ""),
        "postalCode": current.get("postalCode", ""),
        "country": current.get("country", ""),
        "phoneNumbers": current.get("phoneNumbers", []),
        "privacyPolicy": current.get("privacyPolicy", ""),
        "ndisNumber": current.get("ndisNumber", ""),
        "medicareNum": current.get("medicareNum", ""),
        "irn": current.get("irn", ""),
        "veteransFileNumber": current.get("veteransFileNumber", ""),
        "emergencyContactNumber": current.get("emergencyContactNumber", ""),
        "emergencyContactName": current.get("emergencyContactName", ""),
        "emergencyContactRelationship": current.get("emergencyContactRelationship", ""),
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.put(
            f"{SPLOSE_API_BASE}/patients/{patient_id}",
            headers=_headers(api_key),
            json=body,
        )
        response.raise_for_status()
        logger.info("Updated Splose patient id=%s", patient_id)
        return {
            "status": "updated",
            "patient_id": patient_id,
        }


async def search_patients(
    query: str,
    api_key: str,
) -> list[dict]:
    """Search for patients in Splose by name, email, or phone number.

    Returns a list of matching patients with basic info.
    """
    params: dict = {}
    if "@" in query:
        params["email"] = query
    elif query.replace("+", "").replace(" ", "").isdigit():
        # Strip country code for Splose (expects no country code)
        phone = query.replace("+61", "0").replace(" ", "")
        params["phoneNumber"] = phone
    else:
        # Assume name — try first name first
        parts = query.strip().split(maxsplit=1)
        params["firstname"] = parts[0]
        if len(parts) > 1:
            params["lastname"] = parts[1]

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{SPLOSE_API_BASE}/patients",
            headers=_headers(api_key),
            params=params,
        )
        response.raise_for_status()
        data = response.json()
        return [
            {
                "patient_id": p["id"],
                "firstname": p.get("firstname", ""),
                "lastname": p.get("lastname", ""),
                "email": p.get("email"),
                "phone": (
                    p["phoneNumbers"][0]["phoneNumber"]
                    if p.get("phoneNumbers")
                    else None
                ),
            }
            for p in data.get("data", [])
        ]


async def get_practitioners(api_key: str, active_only: bool = True) -> list[dict]:
    """List practitioners in the Splose workspace."""
    params: dict = {}
    if active_only:
        params["isActive"] = "true"

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{SPLOSE_API_BASE}/practitioners",
            headers=_headers(api_key),
            params=params,
        )
        response.raise_for_status()
        data = response.json()
        return [
            {
                "practitioner_id": p["id"],
                "firstname": p.get("firstname", ""),
                "lastname": p.get("lastname", ""),
                "profession": p.get("profession"),
                "email": p.get("email"),
            }
            for p in data.get("data", [])
        ]


async def check_availability(
    practitioner_id: int,
    start_date: str,
    end_date: str,
    api_key: str,
    location_id: int | None = None,
) -> list[dict]:
    """Get practitioner availability for a date range.

    start_date/end_date should be ISO format (YYYY-MM-DDTHH:MM:SS.000Z).
    Max range is 100 days.
    """
    params: dict = {
        "startDate": start_date,
        "endDate": end_date,
    }
    if location_id:
        params["locationId"] = location_id

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{SPLOSE_API_BASE}/availabilities/{practitioner_id}",
            headers=_headers(api_key),
            params=params,
        )
        response.raise_for_status()
        data = response.json()
        return [
            {
                "date": slot["date"],
                "start_time": slot["startTime"],
                "end_time": slot["endTime"],
                "location_id": slot.get("locationId"),
            }
            for slot in data.get("data", [])
        ]


async def create_appointment(
    start: str,
    end: str,
    patient_id: int,
    practitioner_id: int,
    service_id: int,
    location_id: int,
    api_key: str,
    note: str | None = None,
) -> dict:
    """Book an appointment in Splose.

    All IDs (patient, practitioner, service, location) must be valid Splose IDs.
    start/end should be ISO datetimes in UTC.
    """
    body: dict = {
        "start": start,
        "end": end,
        "patientId": patient_id,
        "practitionerId": practitioner_id,
        "serviceId": service_id,
        "locationId": location_id,
    }
    if note:
        body["note"] = note

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{SPLOSE_API_BASE}/appointments",
            headers=_headers(api_key),
            json=body,
        )
        response.raise_for_status()
        data = response.json()
        logger.info("Created Splose appointment id=%s", data.get("id"))
        return {
            "status": "booked",
            "appointment_id": data["id"],
            "start": data.get("start", ""),
            "end": data.get("end", ""),
            "practitioner_id": data.get("practitionerId"),
        }


async def list_appointments(
    api_key: str,
    patient_id: int | None = None,
    practitioner_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """List appointments in Splose with optional filters.

    Args:
        api_key: Splose API key.
        patient_id: Filter by patient.
        practitioner_id: Filter by practitioner.
        start_date: ISO datetime — only appointments after this.
        end_date: ISO datetime — only appointments before this.

    Returns:
        List of appointments with id, start, end, patient/practitioner info.
    """
    params: dict = {}
    if patient_id:
        params["patientId"] = patient_id
    if practitioner_id:
        params["practitionerId"] = practitioner_id
    if start_date:
        params["update_gt"] = start_date
    if end_date:
        params["update_lt"] = end_date

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{SPLOSE_API_BASE}/appointments",
            headers=_headers(api_key),
            params=params,
        )
        response.raise_for_status()
        data = response.json()

    return [
        {
            "appointment_id": appt["id"],
            "start": appt.get("start", ""),
            "end": appt.get("end", ""),
            "practitioner_id": appt.get("practitionerId"),
            "patient_id": appt.get("patientId"),
            "service_id": appt.get("serviceId"),
            "location_id": appt.get("locationId"),
            "note": appt.get("note", ""),
            "status": (
                appt.get("appointmentPatients", [{}])[0].get("status", "")
                if appt.get("appointmentPatients")
                else ""
            ),
        }
        for appt in data.get("data", [])
    ]


async def get_appointment(appointment_id: int, api_key: str) -> dict:
    """Get a single appointment by ID."""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{SPLOSE_API_BASE}/appointments/{appointment_id}",
            headers=_headers(api_key),
        )
        response.raise_for_status()
        return response.json()


async def cancel_appointment(
    appointment_id: int,
    api_key: str,
    reason: str = "",
) -> dict:
    """Cancel an appointment in Splose.

    Uses PUT to update the appointment with cancellation status.

    Args:
        appointment_id: The appointment ID.
        api_key: Splose API key.
        reason: Cancellation reason.

    Returns:
        Dict with status and appointment_id.
    """
    # GET current appointment to get required fields for PUT
    current = await get_appointment(appointment_id, api_key)

    # Build update body — Splose PUT requires the full appointment object
    body: dict = {
        "start": current["start"],
        "end": current["end"],
        "serviceId": current["serviceId"],
        "locationId": current["locationId"],
        "practitionerId": current["practitionerId"],
        "patientId": current["patientId"],
    }

    # Set cancellation on the appointmentPatients array
    if current.get("appointmentPatients"):
        patients = current["appointmentPatients"]
        patients[0]["status"] = "Cancelled"
        if reason:
            patients[0]["cancellationReason"] = reason
        body["appointmentPatients"] = patients

    if current.get("note"):
        body["note"] = current["note"]
    if reason and not body.get("note"):
        body["note"] = f"Cancelled: {reason}"

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.put(
            f"{SPLOSE_API_BASE}/appointments/{appointment_id}",
            headers=_headers(api_key),
            json=body,
        )
        response.raise_for_status()

    logger.info("Cancelled Splose appointment id=%s", appointment_id)
    return {
        "status": "cancelled",
        "appointment_id": appointment_id,
    }
