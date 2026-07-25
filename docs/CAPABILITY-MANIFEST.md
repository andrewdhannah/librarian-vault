{{% for cap in capabilities %}}
## {{cap.name}}

| Field | Value |
|------|-------|
| ID | `{{cap.name}}` |
| Tool | `{{cap.tool}}` |
| Risk | {{cap.risk}} |
| Permission | `{{cap.permission}}` |
| Status | pending (requires activation) |

{{% endfor %}}

## Dependencies

{% if dependencies %}
{% else %}
- None declared
{% endif %}

## Forbidden Actions

| Action | Outcome |
|--------|---------|
| modify_librarian_authority_state | REVOKE |
| create_owner_decisions | REVOKE |
| mutate_sprint_ledger | REVOKE |
| delete_knowledge.vault_artifacts | SUSPENDED |
