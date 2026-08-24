const { Pool } = require('pg');

const pool = new Pool({
  connectionString: 'postgresql://postgres.wyrelouvsoljukftsgxp:bAnHV7LgLl2lr8zQ@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres'
});

const dids = [
  { did: '08037259676', rawDid: '8037259676', camp_id: 64, lead_id: 1079 },
  { did: '08037259675', rawDid: '8037259675', camp_id: 63, lead_id: 1078 },
  { did: '08037259674', rawDid: '8037259674', camp_id: 62, lead_id: 1077 },
  { did: '08037259673', rawDid: '8037259673', camp_id: 61, lead_id: 1076 },
  { did: '08037259672', rawDid: '8037259672', camp_id: 65, lead_id: 1083 }
];

async function seed() {
  for (const d of dids) {
    const meta = JSON.stringify({ camp_id: d.camp_id, lead_id: d.lead_id, raw_did: d.rawDid });
    await pool.query(`
      INSERT INTO did_inventory (
        "didNumber", "displayName", "environment", "provider", "isActive",
        "inboundEnabled", "outboundEnabled", "metadata", "updatedAt"
      ) VALUES ($1, $2, 'staging', 'icallmate', TRUE, TRUE, TRUE, $3::jsonb, NOW())
      ON CONFLICT ("didNumber") DO UPDATE SET
        "metadata" = $3::jsonb,
        "isActive" = TRUE,
        "inboundEnabled" = TRUE,
        "outboundEnabled" = TRUE,
        "updatedAt" = NOW()
    `, [d.did, `iCallMate DID ${d.rawDid}`, meta]);
    console.log(`Seeded DID: ${d.did} | Camp: ${d.camp_id} | Lead: ${d.lead_id}`);
  }

  const res = await pool.query(`SELECT "didNumber", "displayName", "provider", "metadata" FROM did_inventory WHERE "didNumber" LIKE '0803725967%' ORDER BY "didNumber" DESC`);
  console.log('\nAll 5 DIDs in did_inventory:');
  console.table(res.rows);
  await pool.end();
}

seed().catch(err => {
  console.error('Seed error:', err);
  process.exit(1);
});
