"""
Librarian Vault — MCP Server

JSON-RPC 2.0 over HTTP following the Librarian extension model.
This server starts in REGISTERED state. Capabilities require
handshake completion and owner approval to activate.
"""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone

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
        """Return declared tools. Updated when capabilities are activated."""
        return [
            {
                "name": "vault_ingest",
                "description": "Vault Ingest capability",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string", "description": "Input for vault.ingest"}
                    }
                }
            },
            {
                "name": "vault_search",
                "description": "Vault Search capability",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string", "description": "Input for vault.search"}
                    }
                }
            },
            {
                "name": "vault_verify",
                "description": "Vault Verify capability",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string", "description": "Input for vault.verify"}
                    }
                }
            },
            {
                "name": "vault_retrieve",
                "description": "Vault Retrieve capability",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string", "description": "Input for vault.retrieve"}
                    }
                }
            },
            {
                "name": "vault_status",
                "description": "Vault Status capability",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string", "description": "Input for vault.status"}
                    }
                }
            },
        ]

    def _handle_tool(self, tool_name, arguments):
        """Execute a tool. This is where your domain logic goes."""
        # TODO: Implement librarian-vault-extension domain logic
        return {"content": [{"type": "text", "text": f"Tool '{tool_name}' called. Not yet implemented."}]}

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
    print()
    server.serve_forever()


if __name__ == "__main__":
    start_server()
