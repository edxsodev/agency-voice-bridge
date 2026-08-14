import { randomUUID } from "node:crypto";
import express from "express";
import { insertWorkflowBlueprint, assignRandomDidToCompany } from "../database.js";

const router = express.Router();

/**
 * POST /api/v1/voice-agents/provision
 * Provision a full native Piper Workflow Blueprint + Auto-assign DID for a business/agency.
 */
router.post("/api/v1/voice-agents/provision", async (req, res) => {
  const {
    agency_id,
    agency_name,
    website,
    system_prompt,
    callback_url,
    voice_model = "gemini_live",
  } = req.body || {};

  if (!agency_name || !system_prompt) {
    return res.status(400).json({ error: "agency_name and system_prompt are required" });
  }

  const workflowId = `WF_AGENCY_${(agency_id || agency_name).toString().replace(/\W+/g, "_").toUpperCase()}`;
  const blueprintId = randomUUID();
  const companyId = req.body.company_id || "00000000-0000-0000-0000-000000000001";

  // 1. Build native Piper Node Graph for Piper Web Dashboard
  const flowPayload = {
    nodes: [
      {
        id: "trigger-1",
        type: "triggerNode",
        position: { x: 100, y: 100 },
        data: { listenWorkflowId: workflowId, title: "Inbound Call Trigger" },
      },
      {
        id: "voice-1",
        type: "voiceNode",
        position: { x: 100, y: 220 },
        data: {
          voicePrompt: system_prompt,
          voiceModel: voice_model,
          voiceName: "Aoede",
          title: `${agency_name} Receptionist`,
        },
      },
      {
        id: "callback-1",
        type: "callbackNode",
        position: { x: 100, y: 340 },
        data: { callbackWebhookUrl: callback_url || null, title: "Lead Dispatch Webhook" },
      },
    ],
    edges: [
      { id: "e1", source: "trigger-1", target: "voice-1" },
      { id: "e2", source: "voice-1", target: "callback-1" },
    ],
  };

  try {
    // 2. Insert into workflow_blueprints
    await insertWorkflowBlueprint({
      blueprintId,
      companyId,
      workflowName: `${agency_name} (AI Receptionist)`,
      callbackWebhookUrl: callback_url || null,
      voiceProvider: "icallmate",
      voiceModel: voice_model,
      flowPayload,
    });

    // 3. Auto-assign free DID from did_inventory
    let assignedDid = null;
    try {
      const didAssignment = await assignRandomDidToCompany({
        companyId,
        blueprintId,
        workflowId,
        environment: "staging",
      });
      assignedDid = didAssignment?.didNumber || null;
    } catch (e) {
      console.warn("[agency-provision] DID pool assign warning:", e.message);
    }

    return res.json({
      status: "success",
      blueprint_id: blueprintId,
      workflow_id: workflowId,
      agency_name,
      assigned_did: assignedDid || "NO_FREE_DID_IN_POOL",
      display_phone: assignedDid || "Pending DID Pool",
      dashboard_url: `/workflows/${blueprintId}`,
    });
  } catch (error) {
    console.error("[agency-provision] Failed:", error);
    return res.status(500).json({ error: error.message });
  }
});

export default router;
