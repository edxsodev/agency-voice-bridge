import hashlib
import re

import requests


DEFAULT_CAPTURED_FIELDS = [
    "caller_name",
    "phone_number",
    "email",
    "requirement",
    "location",
    "budget",
    "preferred_callback_time",
]


class PiperError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def build_workflow_id(agency_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", agency_id).strip("_").upper()[:32] or "BUSINESS"
    digest = hashlib.sha256(agency_id.encode("utf-8")).hexdigest()[:10].upper()
    return f"AGENCY_{slug}_{digest}"


def build_flow_payload(
    *,
    workflow_id: str,
    agency_name: str,
    prompt: str,
    first_turn_message: str,
    voice_model: str,
    voice_name: str,
) -> dict:
    return {
        "nodes": [
            {
                "id": "trigger-1",
                "type": "triggerNode",
                "position": {"x": 120, "y": 120},
                "data": {
                    "listenWorkflowId": workflow_id,
                    "title": "Inbound Call Trigger",
                },
            },
            {
                "id": "voice-1",
                "type": "voiceNode",
                "position": {"x": 120, "y": 280},
                "data": {
                    "title": f"{agency_name} Receptionist",
                    "voicePrompt": prompt,
                    "firstTurnMessage": first_turn_message,
                    "voiceModel": voice_model,
                    "voiceName": voice_name,
                    "voicePace": 1.0,
                },
            },
        ],
        "edges": [
            {
                "id": "trigger-to-voice",
                "source": "trigger-1",
                "target": "voice-1",
            }
        ],
    }


class PiperClient:
    def __init__(self, base_url: str, admin_email: str, timeout_seconds: float = 15):
        self.base_url = base_url.rstrip("/")
        self.admin_email = admin_email.strip().lower()
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    def _request(self, method: str, path: str, *, payload: dict | None = None, admin: bool = False) -> dict:
        header_name = "x-piper-admin-email" if admin else "x-piper-user-email"
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                json=payload,
                headers={header_name: self.admin_email},
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise PiperError(f"Piper unavailable: {exc}") from exc

        if not response.ok:
            try:
                error_payload = response.json()
                message = error_payload.get("error", {}).get("message") or error_payload.get("error")
            except ValueError:
                message = response.text
            raise PiperError(str(message or f"Piper returned HTTP {response.status_code}"), response.status_code)

        try:
            return response.json()
        except ValueError as exc:
            raise PiperError("Piper returned invalid JSON") from exc

    def list_companies(self) -> list[dict]:
        return self._request("GET", "/api/companies", admin=True).get("companies", [])

    def create_company(self, *, agency_id: str, agency_name: str) -> dict:
        result = self._request(
            "POST",
            "/api/admin/companies",
            payload={
                "adminEmailAddress": self.admin_email,
                "externalCompanyId": agency_id,
                "companyName": agency_name,
            },
            admin=True,
        )
        return result["company"]

    def list_blueprints(self, company_id: str) -> list[dict]:
        result = self._request("GET", f"/api/companies/{company_id}/blueprints")
        return result.get("workflows", result.get("blueprints", []))

    def create_blueprint(self, payload: dict) -> dict:
        return self._request("POST", "/api/blueprints", payload=payload)["workflow"]

    def update_blueprint(self, blueprint_id: str, payload: dict) -> dict:
        return self._request("PUT", f"/api/blueprints/{blueprint_id}", payload=payload)["workflow"]

    def assign_random_did(self, *, company_id: str, blueprint_id: str, workflow_id: str) -> dict:
        result = self._request(
            "POST",
            f"/api/companies/{company_id}/dids/assign",
            payload={
                "adminEmailAddress": self.admin_email,
                "blueprintId": blueprint_id,
                "workflowId": workflow_id,
                "assignmentMode": "company_default",
            },
            admin=True,
        )
        return result["assignment"]

    def provision(
        self,
        *,
        agency_id: str,
        agency_name: str,
        prompt: str,
        callback_url: str | None,
        callback_bearer_token: str | None,
        first_turn_message: str,
        voice_model: str,
        voice_name: str,
    ) -> dict:
        workflow_id = build_workflow_id(agency_id)
        company = next(
            (item for item in self.list_companies() if item.get("externalCompanyId") == agency_id),
            None,
        )
        if not company:
            try:
                company = self.create_company(agency_id=agency_id, agency_name=agency_name)
            except PiperError as exc:
                if exc.status_code != 409:
                    raise
                company = next(
                    (item for item in self.list_companies() if item.get("externalCompanyId") == agency_id),
                    None,
                )
                if not company:
                    raise

        company_id = company["companyId"]
        flow_payload = build_flow_payload(
            workflow_id=workflow_id,
            agency_name=agency_name,
            prompt=prompt,
            first_turn_message=first_turn_message,
            voice_model=voice_model,
            voice_name=voice_name,
        )
        callback_auth_method = "bearer" if callback_bearer_token else "none"
        callback_auth_config = {"token": callback_bearer_token} if callback_bearer_token else None
        common_payload = {
            "companyId": company_id,
            "workflowName": f"{agency_name} AI Receptionist",
            "callbackWebhookUrl": callback_url,
            "callbackPayloadFormat": "workflow",
            "callbackAuthMethod": callback_auth_method,
            "callbackAuthConfig": callback_auth_config,
            "voiceProvider": "icallmate",
            "voiceModel": voice_model,
            "llmProvider": "gemini",
            "flowPayload": flow_payload,
            "capturedFieldsConfig": DEFAULT_CAPTURED_FIELDS,
        }

        workflows = self.list_blueprints(company_id)
        workflow = next(
            (item for item in workflows if item.get("triggerWorkflowId") == workflow_id),
            None,
        )
        did_number = (workflow or {}).get("preferredDidNumber") or company.get("assignedDidNumber")

        if workflow:
            workflow = self.update_blueprint(
                workflow["blueprintId"],
                {**common_payload, "preferredDidNumber": did_number},
            )
        else:
            workflow = self.create_blueprint({**common_payload, "preferredDidNumber": None})

        if not did_number:
            assignment = self.assign_random_did(
                company_id=company_id,
                blueprint_id=workflow["blueprintId"],
                workflow_id=workflow_id,
            )
            did_number = assignment.get("didNumber")
            if not did_number:
                raise PiperError("Piper assigned no DID", 502)
            workflow = self.update_blueprint(
                workflow["blueprintId"],
                {**common_payload, "preferredDidNumber": did_number},
            )

        return {
            "status": "active",
            "agency_id": agency_id,
            "agency_name": agency_name,
            "company_id": company_id,
            "workflow_id": workflow_id,
            "blueprint_id": workflow["blueprintId"],
            "did_number": did_number,
        }
