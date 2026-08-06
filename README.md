# Librarian Vault

**A governed knowledge-vault extension for The Librarian.**

Part of the Librarian add-on ecosystem. The Librarian Vault provides a governed storage, search, and retrieval surface for indexed knowledge with full provenance — the custody layer where ingested knowledge becomes queryable evidence.

> **Boundary:** The vault may store, search, retrieve, and verify knowledge. It may not modify Librarian authority state, create owner decisions, or mutate the sprint ledger.

---

## Status

- **Extension ID:** `librarian-vault-extension`
- **Contract:** `librarian-vault-extension-contract-v1`
- **Domain:** `knowledge.vault`
- **Classification:** knowledge_custody_provider
- **Lifecycle:** Registered — capability activation pending Owner approval
- **Project receipt:** `receipts/registry/pcr-librarian-vault-20260727-001.json`

---

## Capabilities

| Capability | Risk | Tool | Purpose |
|-----------|------|------|---------|
| `vault_ingest` | R1 | `vault_ingest` | Feed an IngestionResult into the vault with provenance |
| `vault_search` | R0 | `vault_search` | Search indexed knowledge, returns results with provenance |
| `vault_retrieve` | R0 | `vault_retrieve` | Retrieve full stored knowledge artifacts |
| `vault_verify` | R0 | `vault_verify` | Verify artifact integrity and provenance chain |
| `vault_status` | R0 | `vault_status` | Report vault state and indexing health |
| `vault_artifacts` | R0 | `vault_artifacts` | List stored artifacts |

### Forbidden Actions

| Action | Outcome |
|--------|---------|
| `modify_librarian_authority_state` | REVOKE |
| `create_owner_decisions` | REVOKE |
| `mutate_sprint_ledger` | REVOKE |
| `delete_knowledge.vault_artifacts` | SUSPENDED |

---

## Quick Start

```bash
# Start the MCP server (REGISTERED state)
python3 src/mcp/server.py

# Run validation
python3 -m src.validation.fixture_runner
```

## Key Files

| File | Purpose |
|------|---------|
| `docs/PROJECT-IDENTITY.md` | Extension identity and purpose |
| `docs/EXTENSION-CONTRACT.json` | Contract document |
| `docs/CAPABILITY-MANIFEST.md` | Capability descriptions |
| `docs/EXTENSION-STATUS.md` | Generated status from Librarian state |
| `mcp/capabilities.json` | Capability manifest |
| `mcp/permissions.json` | Permission boundaries |
| `src/mcp/server.py` | MCP server (tools/list + tools/call) |
| `src/handshake/` | Lifecycle state machine |

## Compliance

Before requesting activation, ensure:

- [ ] Identity document matches contract
- [ ] Capability manifest matches implementation
- [ ] Contract has all required sections
- [ ] MCP server starts and responds
- [ ] Handshake completes to REGISTERED
- [ ] Validation suite passes

---

## License

MIT
