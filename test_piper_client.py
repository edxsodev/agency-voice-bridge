import unittest

from piper_client import PiperClient, build_flow_payload, build_workflow_id


class FakePiperClient(PiperClient):
    def __init__(self):
        self.companies = []
        self.workflows = {}
        self.assignments = 0

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

    def assign_random_did(self, *, company_id, blueprint_id, workflow_id):
        self.assignments += 1
        self.companies[0]["assignedDidNumber"] = "919999999999"
        return {"didNumber": "919999999999"}


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
        }
        first = client.provision(**args)
        second = client.provision(**{**args, "prompt": "Updated Acme Realty persona prompt."})
        self.assertEqual(first["blueprint_id"], second["blueprint_id"])
        self.assertEqual(first["did_number"], second["did_number"])
        self.assertEqual(client.assignments, 1)
        self.assertEqual(len(client.workflows), 1)


if __name__ == "__main__":
    unittest.main()
