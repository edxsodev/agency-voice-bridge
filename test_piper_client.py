import unittest

from piper_client import PiperClient, build_flow_payload, build_kyc_prompt, build_workflow_id, select_pool_did


class FakePiperClient(PiperClient):
    def __init__(self):
        self.companies = []
        self.workflows = {}
        self.assignments = 0
        self.synced_dids = []

    def list_companies(self):
        return self.companies

    def create_company(self, *, agency_id, agency_name):
        company = {
            "companyId": "00000000-0000-4000-8000-000000000001",
            "companyName": agency_name,
            "externalCompanyId": agency_id,
            "assignedDidNumber": None,
        }
        self.companies.append(company)
        return company

    def list_blueprints(self, company_id):
        return list(self.workflows.values())

    def create_blueprint(self, payload):
        workflow = {
            **payload,
            "blueprintId": "00000000-0000-4000-8000-000000000002",
            "triggerWorkflowId": payload["flowPayload"]["nodes"][0]["data"]["listenWorkflowId"],
        }
        self.workflows[workflow["blueprintId"]] = workflow
        return workflow

    def update_blueprint(self, blueprint_id, payload):
        workflow = {
            **self.workflows[blueprint_id],
            **payload,
            "blueprintId": blueprint_id,
        }
        self.workflows[blueprint_id] = workflow
        return workflow

    def list_dids(self):
        return [{
            "didNumber": "919999999999",
            "isAvailable": True,
            "isActive": True,
            "inboundEnabled": True,
            "provider": "iCallMate",
        }]

    def assign_did(self, *, company_id, blueprint_id, workflow_id, did_number):
        self.assignments += 1
        self.companies[0]["assignedDidNumber"] = did_number
        return {"didNumber": did_number}

    def sync_did_macro(self, did_number):
        self.synced_dids.append(did_number)


class ProvisioningTests(unittest.TestCase):
    def test_workflow_id_is_stable_and_collision_resistant(self):
        self.assertEqual(build_workflow_id("agency 1"), build_workflow_id("agency 1"))
        self.assertNotEqual(build_workflow_id("agency 1"), build_workflow_id("agency-1"))

    def test_flow_contains_brand_prompt(self):
        flow = build_flow_payload(
            workflow_id="AGENCY_1",
            agency_name="Acme",
            prompt="Brand persona prompt",
            first_turn_message="Hello",
            voice_model="gemini_live",
            voice_name="Aoede",
        )
        self.assertEqual(flow["nodes"][1]["data"]["voicePrompt"], "Brand persona prompt")

    def test_default_voice_pace_is_1_3(self):
        flow = build_flow_payload(
            workflow_id="AGENCY_1",
            agency_name="Acme",
            prompt="Brand persona prompt",
            first_turn_message="Hello",
            voice_model="sarvam",
            voice_name="neha",
        )
        self.assertEqual(flow["nodes"][1]["data"]["voicePace"], 1.3)

    def test_kyc_prompt_contains_authoritative_company_context(self):
        prompt = build_kyc_prompt(
            agency_name="Acme Realty",
            kyc={"service_area": "Austin", "phone": "+1 555 0100"},
            knowledge_base={"a": "Residential sales", "b": "Buyer support", "c": "Local listings"},
            location="Austin, TX",
            workflow="Answer inbound property inquiries",
            workflow_type="inbound_reception",
        )
        self.assertIn("Acme Realty", prompt)
        self.assertIn("Austin", prompt)
        self.assertIn("Residential sales", prompt)
        self.assertIn("inbound_reception", prompt)

    def test_repeat_provision_reuses_workflow_and_did(self):
        client = FakePiperClient()
        args = {
            "agency_id": "agency-1",
            "agency_name": "Acme Realty",
            "prompt": "You are Acme Realty receptionist.",
            "callback_url": "https://example.com/callback",
            "callback_bearer_token": "callback-secret",
            "first_turn_message": "Hello from Acme",
            "voice_model": "gemini_live",
            "voice_name": "Aoede",
            "did_pool": ["919999999999"],
        }
        first = client.provision(**args)
        second = client.provision(**{**args, "prompt": "Updated Acme Realty persona prompt."})
        self.assertEqual(first["blueprint_id"], second["blueprint_id"])
        self.assertEqual(first["did_number"], second["did_number"])
        self.assertEqual(client.assignments, 1)
        self.assertEqual(client.synced_dids, ["919999999999", "919999999999"])
        self.assertEqual(len(client.workflows), 1)

    def test_pool_uses_order_then_oldest_assignment(self):
        pool = ["1", "2"]
        self.assertEqual(select_pool_did([
            {"didNumber": "2", "isAvailable": True},
            {"didNumber": "1", "isAvailable": True},
        ], pool)["didNumber"], "1")
        self.assertEqual(select_pool_did([
            {"didNumber": "1", "isAvailable": False, "assignment": {"assignedAt": "2026-01-01"}},
            {"didNumber": "2", "isAvailable": False, "assignment": {"assignedAt": "2026-02-01"}},
        ], pool)["didNumber"], "1")


if __name__ == "__main__":
    unittest.main()
