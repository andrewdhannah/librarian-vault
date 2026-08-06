"""
Librarian Vault — MCP Server

JSON-RPC 2.0 over HTTP following the Librarian extension model.
This server starts in REGISTERED state. Capabilities require
handshake completion and owner approval to activate.

KVAI-002: Wired to tools/vault.py — actual domain logic executes here.
"""

import json
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.tools.vault import call_tool, TOOLS

EXTENSION_ID = "librarian-vault-extension"
VERSION = "0.1.0"
MCP_PORT = 9002


class MCPHandler(BaseHTTPRequestHandler):
    """MCP request handler. Implements tools/list and tools/call."""

    def do_POST(self):
        if self.path != "/mcp":
            self._send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"

        try:
            request = json.loads(body)
        except json.JSONDecodeError:
            self._send_json({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None})
            return

        method = request.get("method")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "tools/list":
            self._send_json({"jsonrpc": "2.0", "id": req_id, "result": {"tools": self._get_tools()}})
        elif method == "tools/call":
            tool_name = params.get("name") if isinstance(params, dict) else None
            arguments = params.get("arguments", {}) if isinstance(params, dict) else {}
            self._send_json({"jsonrpc": "2.0", "id": req_id, "result": self._handle_tool(tool_name, arguments)})
        else:
            self._send_json({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}})

    def _get_tools(self):
        """Return declared tools — must match TOOLS router in tools/vault.py."""
        return [
            {
                "name": "vault_ingest",
                "description": "Feed an IngestionResult into the vault. Accepts ingestion_result, source_extension, receipt_id.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ingestion_result": {"type": "object", "description": "IngestionResult dict from source extension"},
                        "source_extension": {"type": "string", "description": "ID of the source extension"},
                        "receipt_id": {"type": "string", "description": "Optional receipt ID from validation"}
                    },
                    "required": ["ingestion_result"]
                }
            },
            {
                "name": "vault_search",
                "description": "Search indexed knowledge. Returns results with provenance.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query string"},
                        "limit": {"type": "integer", "description": "Maximum results (default: 10)"},
                        "min_score": {"type": "number", "description": "Minimum relevance score (default: 0.1)"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "vault_retrieve",
                "description": "Retrieve context for a query with full provenance and citations.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "User query"},
                        "max_chunks": {"type": "integer", "description": "Maximum chunks to retrieve (default: 5)"},
                        "min_score": {"type": "number", "description": "Minimum relevance score (default: 0.1)"},
                        "include_citations": {"type": "boolean", "description": "Include citation details (default: true)"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "vault_verify",
                "description": "Verify provenance of a chunk or artifact. Checks source extension, receipt, content hash, evidence path.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "chunk_id": {"type": "string", "description": "Verify a specific chunk"},
                        "artifact_id": {"type": "string", "description": "Verify all chunks in an artifact"}
                    }
                }
            },
            {
                "name": "vault_status",
                "description": "Get vault statistics: artifact count, chunk count, embedding count, verification status.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "vault_artifacts",
                "description": "List indexed artifacts with metadata.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Maximum artifacts to return (default: 50)"}
                    }
                }
            },
        ]

    def _handle_tool(self, tool_name, arguments):
        """Execute a tool via tools/vault.py:call_tool()."""
        return call_tool(tool_name, arguments)

    def _send_json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code):
        self.send_response(code)
        self.end_headers()


def start_server():
    server = HTTPServer(("127.0.0.1", MCP_PORT), MCPHandler)
    print(f"Librarian Vault MCP Server")
    print(f"  Extension: {EXTENSION_ID}")
    print(f"  Version:   {VERSION}")
    print(f"  State:     REGISTERED (handshake required)")
    print(f"  Endpoint:  http://127.0.0.1:{MCP_PORT}/mcp")
    print(f"  Tools:     {len(TOOLS)} ({', '.join(TOOLS.keys())})")
    print()
    server.serve_forever()


if __name__ == "__main__":
    start_server()
