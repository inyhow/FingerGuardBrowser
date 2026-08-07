"""MCP (Model Context Protocol) server for AI agent integration.

Exposes 8 tools that AI agents (Claude, Cursor, Codex, Gemini) can call
via JSON-RPC over stdio to control FingerGuardBrowser.

Security:
- Does not expose delete-profile via MCP (prevent accidental data loss by AI agents)
- Does not include API key in MCP config text
- All operations are logged

Reference: xiaohei-Chrome V15 MCP Server (8 tools).
"""

import json
import sys
import os
import time
from typing import Dict, Any, Optional
from loguru import logger


class MCPServer:
    """MCP server exposing FingerGuardBrowser tools to AI agents via JSON-RPC over stdio."""

    TOOLS = [
        {
            "name": "list_profiles",
            "description": "List all browser profiles with their status (running/stopped).",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "create_profile",
            "description": "Create a new isolated browser profile with auto-generated fingerprint.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Unique profile name"},
                    "proxy": {"type": "string", "description": "Proxy URL (e.g., socks5://host:port)"},
                    "timezone": {"type": "string", "description": "IANA timezone (e.g., America/New_York)"},
                    "os_type": {"type": "string", "enum": ["windows", "macos", "linux"]},
                },
                "required": ["name"],
            },
        },
        {
            "name": "update_profile",
            "description": "Update an existing profile's settings (proxy, timezone, fingerprint options).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Profile name to update"},
                    "proxy": {"type": "string"},
                    "timezone": {"type": "string"},
                    "webrtc": {"type": "string", "enum": ["filter", "disable", "reveal"]},
                    "canvas_fp": {"type": "boolean"},
                    "webgl_fp": {"type": "boolean"},
                    "audio_fp": {"type": "boolean"},
                },
                "required": ["name"],
            },
        },
        {
            "name": "launch_browser",
            "description": "Launch a browser instance for a profile. Returns the CDP endpoint URL for automation.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Profile name to launch"},
                },
                "required": ["name"],
            },
        },
        {
            "name": "stop_browser",
            "description": "Stop a running browser instance.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Profile name to stop"},
                },
                "required": ["name"],
            },
        },
        {
            "name": "get_sessions",
            "description": "Query active browser sessions and their CDP endpoints.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "check_proxy",
            "description": "Validate proxy connectivity and get exit IP, country, ISP information.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "proxy": {"type": "string", "description": "Proxy URL to validate"},
                },
                "required": ["proxy"],
            },
        },
        {
            "name": "generate_fingerprint",
            "description": "Generate a new fingerprint configuration. Supports AI-powered generation from natural language.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Profile name for the fingerprint"},
                    "os_type": {"type": "string", "enum": ["windows", "macos", "linux"]},
                    "description": {"type": "string", "description": "Natural language description for AI generation (e.g., 'mid-range Windows laptop in New York')"},
                },
                "required": ["name"],
            },
        },
    ]

    def __init__(self, browser_manager=None, proxy_pool=None,
                 fingerprint_manager=None, ai_generator=None, database=None):
        if database is None:
            from ..storage.database import Database
            database = Database()
        self.db = database
        self.bm = browser_manager
        self.pp = proxy_pool
        self.fm = fingerprint_manager
        self.ai = ai_generator

    def run(self):
        """Run the MCP server, reading JSON-RPC from stdin and writing to stdout."""
        logger.info("MCP server started (JSON-RPC over stdio)")

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = self._handle_request(request)
                if response:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()
            except json.JSONDecodeError:
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": "Parse error"},
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()
            except Exception as e:
                logger.error(f"MCP error: {e}")
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32603, "message": str(e)},
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()

    def _handle_request(self, request: dict) -> Optional[dict]:
        """Handle a single JSON-RPC request."""
        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        # === Initialize ===
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": False},
                    },
                    "serverInfo": {
                        "name": "FingerGuardBrowser MCP",
                        "version": "2.0.0",
                    },
                }
            }

        # === List tools ===
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": self.TOOLS,
                }
            }

        # === Call tool ===
        if method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = self._call_tool(tool_name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, indent=2, ensure_ascii=False),
                    }]
                }
            }

        # === Notifications (no response) ===
        if method == "notifications/initialized":
            return None

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    def _call_tool(self, tool_name: str, args: dict) -> dict:
        """Execute a tool and return the result."""
        logger.info(f"MCP tool called: {tool_name} with args: {args}")

        if tool_name == "list_profiles":
            return self._tool_list_profiles(args)

        elif tool_name == "create_profile":
            return self._tool_create_profile(args)

        elif tool_name == "update_profile":
            return self._tool_update_profile(args)

        elif tool_name == "launch_browser":
            return self._tool_launch_browser(args)

        elif tool_name == "stop_browser":
            return self._tool_stop_browser(args)

        elif tool_name == "get_sessions":
            return self._tool_get_sessions(args)

        elif tool_name == "check_proxy":
            return self._tool_check_proxy(args)

        elif tool_name == "generate_fingerprint":
            return self._tool_generate_fingerprint(args)

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    def _tool_list_profiles(self, args: dict) -> dict:
        profiles = self.db.list_profiles()
        return {
            "count": len(profiles),
            "profiles": [{
                "name": p["name"],
                "is_running": p["is_running"],
                "proxy": "***" if p.get("proxy") else None,
                "timezone": p.get("timezone"),
                "cdp_endpoint": p.get("cdp_endpoint") if p["is_running"] else None,
            } for p in profiles]
        }

    def _tool_create_profile(self, args: dict) -> dict:
        name = args.get("name")
        if not name:
            return {"error": "name is required"}

        kwargs = {}
        for key in ["proxy", "timezone", "os_type"]:
            if key in args:
                kwargs[key] = args[key]

        try:
            profile = self.db.create_profile(name, **kwargs)
            # Generate fingerprint if fingerprint manager is available
            if self.fm and "os_type" in kwargs:
                self.fm.create_fingerprint(name, os_type=kwargs["os_type"])
            elif self.fm:
                self.fm.create_fingerprint(name)

            return {"status": "created", "name": name, "profile": {
                "name": profile["name"],
                "timezone": profile.get("timezone"),
                "is_running": False,
            }}
        except Exception as e:
            return {"error": str(e)}

    def _tool_update_profile(self, args: dict) -> dict:
        name = args.get("name")
        if not name:
            return {"error": "name is required"}

        update_fields = {k: v for k, v in args.items() if k != "name"}
        profile = self.db.update_profile(name, **update_fields)
        if not profile:
            return {"error": f"Profile '{name}' not found"}
        return {"status": "updated", "name": name}

    def _tool_launch_browser(self, args: dict) -> dict:
        name = args.get("name")
        if not name:
            return {"error": "name is required"}

        if not self.bm:
            return {"error": "Browser manager not configured"}

        try:
            self.bm.launch_browser(name)
            cdp = self.bm.get_cdp_endpoint(name)
            return {
                "status": "launched",
                "name": name,
                "cdp_endpoint": cdp,
                "note": f"Use the CDP endpoint with Selenium/Puppeteer/Playwright for automation: "
                        f"browser = await puppeteer.connect({{browserWSEndpoint: '{cdp}'}})"
            }
        except Exception as e:
            return {"error": str(e)}

    def _tool_stop_browser(self, args: dict) -> dict:
        name = args.get("name")
        if not name:
            return {"error": "name is required"}

        if not self.bm:
            return {"error": "Browser manager not configured"}

        try:
            self.bm.close_browser(name)
            return {"status": "stopped", "name": name}
        except Exception as e:
            return {"error": str(e)}

    def _tool_get_sessions(self, args: dict) -> dict:
        profiles = self.db.list_profiles()
        running = [p for p in profiles if p["is_running"]]
        return {
            "count": len(running),
            "sessions": [{
                "name": p["name"],
                "cdp_endpoint": p.get("cdp_endpoint"),
                "last_used": p.get("last_used"),
            } for p in running]
        }

    def _tool_check_proxy(self, args: dict) -> dict:
        proxy = args.get("proxy")
        if not proxy:
            return {"error": "proxy is required"}

        if self.bm:
            result = self.bm.check_proxy(proxy)
            # Mask proxy credentials in response
            if "ip" in result:
                return {
                    "status": result.get("status"),
                    "ip": result.get("ip"),
                    "country": result.get("country"),
                    "country_code": result.get("country_code"),
                    "city": result.get("city"),
                    "isp": result.get("isp"),
                    "timezone": result.get("timezone"),
                }
            return result
        return {"error": "Browser manager not configured"}

    def _tool_generate_fingerprint(self, args: dict) -> dict:
        name = args.get("name")
        if not name:
            return {"error": "name is required"}

        description = args.get("description")
        os_type = args.get("os_type")

        if description and self.ai:
            config = self.ai.generate_from_natural_language(description)
            fingerprint = self.ai.generate_fingerprint_config(config, profile_name=name)
            return {
                "status": "generated",
                "name": name,
                "method": "ai_powered",
                "consistency_score": config.get("consistency_score"),
                "fingerprint_summary": {
                    "os_type": fingerprint.get("os_type"),
                    "user_agent": fingerprint.get("navigator", {}).get("userAgent"),
                    "platform": fingerprint.get("navigator", {}).get("platform"),
                    "hardware_concurrency": fingerprint.get("navigator", {}).get("hardwareConcurrency"),
                    "device_memory": fingerprint.get("navigator", {}).get("deviceMemory"),
                    "timezone": fingerprint.get("timezone"),
                    "webgl_renderer": fingerprint.get("webgl", {}).get("unmaskedRenderer"),
                }
            }
        elif self.fm:
            fingerprint = self.fm.create_fingerprint(name, os_type=os_type)
            return {
                "status": "generated",
                "name": name,
                "method": "rule_based",
                "fingerprint_summary": {
                    "os_type": fingerprint.get("os_type"),
                    "user_agent": fingerprint.get("navigator", {}).get("userAgent"),
                    "platform": fingerprint.get("navigator", {}).get("platform"),
                    "hardware_concurrency": fingerprint.get("navigator", {}).get("hardwareConcurrency"),
                    "device_memory": fingerprint.get("navigator", {}).get("deviceMemory"),
                    "timezone": fingerprint.get("timezone"),
                }
            }
        else:
            return {"error": "Fingerprint manager not configured"}


def main():
    """Entry point for running MCP server standalone."""
    # Initialize components
    from ..storage.database import Database
    from ..fingerprint.fingerprint_manager import FingerprintManager
    from ..fingerprint.ai_generator import AIFingerprintGenerator

    db = Database()
    fm = FingerprintManager()
    ai = AIFingerprintGenerator(fingerprint_manager=fm)

    server = MCPServer(
        database=db,
        fingerprint_manager=fm,
        ai_generator=ai,
    )
    server.run()


if __name__ == "__main__":
    main()
