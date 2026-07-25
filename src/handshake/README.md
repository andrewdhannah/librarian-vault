"""
Librarian Vault — Handshake Lifecycle

Implements the 6-state lifecycle machine starting at REGISTERED.
Copy the handshake implementation from the Working Bibliography reference:

  github.com/andrewdhannah/working-bibliography-extension/src/handshake/
"""

# Key files to copy from reference:
# - identity.py:     Extension identity announcement and validation
# - validator.py:    Contract and capability manifest validation
# - lifecycle.py:    6-state state machine (REGISTERED through REVOKED)
# - orchestrator.py: Full handshake sequence
# - receipts.py:     Handshake receipts

# After copying, initialize state:
#   lifecycle.initialize_state("librarian-vault-extension")
#   → REGISTERED
#
# Then complete handshake:
#   orchestrator.execute_full_handshake(announcement)
#   → CONTRACT_VERIFIED
#
# Then await owner approval:
#   orchestrator.approve_and_activate("librarian-vault-extension")
#   → OWNER_APPROVED → ACTIVE
