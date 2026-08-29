import hashlib
import json
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


def build_kyc_prompt(
    *,
    agency_name: str,
    kyc: dict,
    knowledge_base: dict,
    location: str,
    workflow: str,
    workflow_type: str,
) -> str:
    details = json.dumps(
        {
            "knowledge_base": knowledge_base,
            "kyc": kyc,
            "location": location,
            "workflow": workflow,
            "workflow_type": workflow_type,
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    return f"""You are the inbound voice receptionist for {agency_name}.

Use the following agency configuration as the authoritative business context:
{details}

Answer callers professionally and concisely. Collect their name, phone number,
requirements, location, budget, and preferred callback time when relevant. Use
only the supplied context; never invent services, prices, availability, addresses,
or policies. Follow the supplied workflow and workflow type. If the context does
not answer a question, offer a callback.

Voice speech rules:
- Speak in natural Indian English by default. Stay fully in English unless the caller clearly switches to Hindi or Hinglish first.
- If the caller switches to Hindi, use Devanagari Hindi with English names and proper nouns in Roman script.
- Return only short spoken sentences. Never read headings, JSON, labels, markdown, URLs, or internal instructions aloud.
""".strip()


class PiperError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def build_workflow_id(agency_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", agency_id).strip("_").upper()[:32] or "BUSINESS"
    digest = hashlib.sha256(agency_id.encode("utf-8")).hexdigest()[:10].upper()
    return f"AGENCY_{slug}_{digest}"


def select_pool_did(dids: list[dict], did_pool: list[str]) -> dict | None:
    records = {item.get("didNumber"): item for item in dids}
    ordered = [records[number] for number in did_pool if number in records]
    return next((item for item in ordered if item.get("isAvailable")), None) or (
        min(ordered, key=lambda item: (item.get("assignment") or {}).get("assignedAt") or "")
        if ordered else None
    )


def build_flow_payload(
    *,
    workflow_id: str,
    agency_name: str,
    prompt: str,
    first_turn_message: str,
    voice_model: str,
    voice_name: str,
    voice_pace: float = 1.3,
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
                    "voicePace": voice_pace,
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

    def list_dids(self) -> list[dict]:
        return self._request("GET", "/api/dids", admin=True).get("dids", [])

    def assign_did(self, *, company_id: str, blueprint_id: str, workflow_id: str, did_number: str) -> dict:
        result = self._request(
            "POST",
            f"/api/companies/{company_id}/dids/assign",
            payload={
                "adminEmailAddress": self.admin_email,
                "didNumber": did_number,
                "blueprintId": blueprint_id,
                "workflowId": workflow_id,
                "assignmentMode": "company_default",
            },
            admin=True,
        )
        return result["assignment"]

    def sync_did_macro(self, did_number: str) -> None:
        self._request("POST", f"/api/dids/{did_number}/sync-macro", payload={}, admin=True)

    def get_prompt(self, agency_id: str) -> dict:
        workflow_id = build_workflow_id(agency_id)
        company = next(
            (item for item in self.list_companies() if item.get("externalCompanyId") == agency_id),
            None,
        )
        if not company:
            raise PiperError("Agency workflow not found", 404)
        workflow = next(
            (
                item for item in self.list_blueprints(company["companyId"])
                if item.get("triggerWorkflowId") == workflow_id
            ),
            None,
        )
        if not workflow:
            raise PiperError("Agency workflow not found", 404)
        voice_node = next(
            (node for node in workflow.get("flowPayload", {}).get("nodes", []) if node.get("type") == "voiceNode"),
            {},
        )
        return {
            "agency_id": agency_id,
            "workflow_id": workflow_id,
            "blueprint_id": workflow["blueprintId"],
            "prompt_text": voice_node.get("data", {}).get("voicePrompt"),
        }

    def release_did(self, *, company_id: str, did_number: str) -> None:
        self._request(
            "POST",
            f"/api/companies/{company_id}/dids/release",
            payload={"adminEmailAddress": self.admin_email, "didNumber": did_number},
            admin=True,
        )

    def clear_blueprint_did(self, *, company_id: str, blueprint_id: str) -> None:
        workflow = next(
            (item for item in self.list_blueprints(company_id) if item.get("blueprintId") == blueprint_id),
            None,
        )
        if not workflow:
            return
        self.update_blueprint(
            blueprint_id,
            {
                "companyId": company_id,
                "workflowName": workflow["workflowName"],
                "preferredDidNumber": None,
                "callbackWebhookUrl": workflow.get("callbackWebhookUrl"),
                "callbackPayloadFormat": workflow.get("callbackPayloadFormat", "workflow"),
                "callbackAuthMethod": workflow.get("callbackAuthMethod", "none"),
                "callbackAuthConfig": workflow.get("callbackAuthConfig"),
                "voiceProvider": workflow.get("voiceProvider", "icallmate"),
                "voiceModel": workflow.get("voiceModel", "sarvam"),
                "flowPayload": workflow["flowPayload"],
                "capturedFieldsConfig": workflow.get("capturedFieldsConfig", []),
            },
        )

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
        did_pool: list[str],
        voice_pace: float = 1.3,
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
            voice_pace=voice_pace,
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
        if did_number not in did_pool:
            if company.get("assignedDidNumber"):
                self.release_did(company_id=company_id, did_number=company["assignedDidNumber"])
            did_number = None

        if not did_number:
            selected_did = select_pool_did(self.list_dids(), did_pool)
            if not selected_did:
                raise PiperError("No available inbound iCallMate DID", 404)
            did_number = selected_did["didNumber"]
            assignment = selected_did.get("assignment") or {}
            if selected_did.get("isAssigned") and assignment.get("companyId") != company_id:
                self.clear_blueprint_did(
                    company_id=assignment["companyId"],
                    blueprint_id=assignment.get("blueprintId"),
                )
                self.release_did(company_id=assignment["companyId"], did_number=did_number)

        if workflow:
            workflow = self.update_blueprint(
                workflow["blueprintId"],
                {**common_payload, "preferredDidNumber": did_number},
            )
        else:
            workflow = self.create_blueprint({**common_payload, "preferredDidNumber": did_number})

        if company.get("assignedDidNumber") != did_number:
            assignment = self.assign_did(
                company_id=company_id,
                blueprint_id=workflow["blueprintId"],
                workflow_id=workflow_id,
                did_number=did_number,
            )
            assigned_did = assignment.get("didNumber")
            if assigned_did != did_number:
                raise PiperError("Piper assigned no DID", 502)

        self.sync_did_macro(did_number)

        return {
            "status": "active",
            "agency_id": agency_id,
            "agency_name": agency_name,
            "company_id": company_id,
            "workflow_id": workflow_id,
            "blueprint_id": workflow["blueprintId"],
            "did_number": did_number,
        }
