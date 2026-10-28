#!/usr/bin/env python3
"""
scripts/verify_stack.py — Full-Stack Verification & Deployment Validation Script

Validates:
1. Default tool registrations and metadata in ai-service
2. PostgreSQL database connectivity and pgvector extension
3. Docker Compose base and full-profile configurations
4. Telemetry and observability in-memory subsystem
5. Service health endpoints (probing live or reporting readiness)

Exit codes:
- 0: All required checks passed successfully
- 1: One or more required checks failed
- 2: Live service probe failed (when --require-live is passed)
"""

import argparse
import asyncio
import os
import shutil
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

# Ensure root and ai-service are on python path
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
AI_SERVICE_DIR = REPO_ROOT / "ai-service"

if str(AI_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Load .env files from both repo root and ai-service
try:
    from dotenv import load_dotenv

    root_env = REPO_ROOT / ".env"
    ai_env = AI_SERVICE_DIR / ".env"
    if root_env.exists():
        load_dotenv(root_env, override=False)
    if ai_env.exists():
        load_dotenv(ai_env, override=False)
except ImportError:
    pass

# Color helpers for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


class StackVerifier:
    def __init__(self, require_live: bool = False, skip_db: bool = False):
        self.require_live = require_live
        self.skip_db = skip_db
        self.passed_count = 0
        self.failed_count = 0
        self.warn_count = 0

    def log_pass(self, title: str, details: str = ""):
        self.passed_count += 1
        msg = f"  {GREEN}[PASS]{RESET} {title}"
        if details:
            msg += f" - {details}"
        print(msg)

    def log_fail(self, title: str, details: str = ""):
        self.failed_count += 1
        msg = f"  {RED}[FAIL]{RESET} {title}"
        if details:
            msg += f" - {details}"
        print(msg)

    def log_warn(self, title: str, details: str = ""):
        self.warn_count += 1
        msg = f"  {YELLOW}[WARN]{RESET} {title}"
        if details:
            msg += f" - {details}"
        print(msg)

    def log_info(self, title: str, details: str = ""):
        msg = f"  {CYAN}[INFO]{RESET} {title}"
        if details:
            msg += f" - {details}"
        print(msg)

    # -------------------------------------------------------------------------
    # 1. Tool Registry Verification
    # -------------------------------------------------------------------------
    def check_tool_registry(self):
        print(f"\n{BOLD}1. Verifying Tool Registrations & AI Capabilities...{RESET}")
        try:
            from app.tools.project_tools import create_default_tool_registry
            from app.tools.base import PermissionLevel

            registry = create_default_tool_registry(str(REPO_ROOT))
            tools_list = registry.list_tools()
            tool_names = [t["name"] for t in tools_list]

            # Core required tools
            required_tools = ["read_file", "list_files", "search_code", "inspect_file"]
            missing_core = [t for t in required_tools if t not in tool_names]

            if missing_core:
                self.log_fail("Core Tool Registration", f"Missing core tools: {missing_core}")
            else:
                self.log_pass("Core Tool Registration", f"Found all core tools: {required_tools}")

            # Verify schema and permission definition
            for t in tools_list:
                if not t.get("name") or not t.get("description") or not t.get("permission") or not isinstance(t.get("input_schema"), dict):
                    self.log_fail(f"Tool Schema: {t.get('name')}", "Invalid tool metadata dictionary")
                    return
            self.log_pass("Tool Metadata & Schemas", f"Verified schema for {len(tools_list)} registered tools")

            # Check optional tools
            opt_present = [t for t in ["git_info", "semantic_search", "search_memory"] if t in tool_names]
            self.log_info("Optional/Extended Tools", f"Active: {opt_present}")

        except Exception as e:
            self.log_fail("Tool Registry Inspection", f"Exception raised: {type(e).__name__}: {e}")

    # -------------------------------------------------------------------------
    # 2. Database & pgvector Connectivity
    # -------------------------------------------------------------------------
    async def check_database(self):
        print(f"\n{BOLD}2. Verifying PostgreSQL & pgvector Database Connectivity...{RESET}")
        if self.skip_db:
            self.log_warn("Database Check", "Skipped as requested via --skip-db flag")
            return

        try:
            from app.config import settings
            from app.db import get_engine, dispose_database_engine
            from sqlalchemy import text

            db_url = settings.database_url.get_secret_value()
            if not db_url:
                self.log_fail("Database URL", "DATABASE_URL is not configured in settings")
                return

            # Mask credentials for logging
            masked_url = db_url.split("@")[-1] if "@" in db_url else "configured"
            self.log_info("Database Target", f"Connecting to host/db: {masked_url}")

            engine = get_engine()
            async with engine.begin() as conn:
                # Check pgvector extension
                res = await conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'"))
                ext_row = res.fetchone()
                if ext_row:
                    self.log_pass("pgvector Extension", "Extension 'vector' is installed and active")
                else:
                    self.log_fail("pgvector Extension", "Extension 'vector' not found in database")

                # Check project knowledge and memory tables
                res = await conn.execute(
                    text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
                )
                tables = [r[0] for r in res.fetchall()]
                expected_tables = ["project_knowledge", "long_term_memory"]
                found_tables = [t for t in expected_tables if t in tables]

                if len(found_tables) == len(expected_tables):
                    self.log_pass("Database Tables", f"Found required schema tables: {found_tables}")
                elif found_tables:
                    self.log_warn("Database Tables", f"Partially initialized: found {found_tables}, expected {expected_tables}")
                else:
                    self.log_warn("Database Tables", "No companion tables found yet (run schema init if first time)")

            await dispose_database_engine()

        except Exception as e:
            self.log_fail("Database Connectivity", f"Connection failed: {type(e).__name__}: {e}")

    # -------------------------------------------------------------------------
    # 3. Docker Compose & Container Infrastructure
    # -------------------------------------------------------------------------
    def check_docker_compose(self):
        print(f"\n{BOLD}3. Verifying Docker & Container Infrastructure...{RESET}")
        if not shutil.which("docker"):
            self.log_warn("Docker Executable", "docker CLI not found in PATH")
            return

        # 3a. Validate base compose config
        try:
            res_base = subprocess.run(
                ["docker", "compose", "config", "--quiet"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=15,
            )
            if res_base.returncode == 0:
                self.log_pass("Docker Compose (Base)", "Base configuration syntax is valid (postgres service)")
            else:
                self.log_fail("Docker Compose (Base)", f"Invalid syntax: {res_base.stderr.strip()}")
        except Exception as e:
            self.log_fail("Docker Compose (Base)", f"Execution error: {e}")

        # 3b. Validate full profile compose config
        try:
            res_full = subprocess.run(
                ["docker", "compose", "--profile", "full", "config", "--quiet"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=15,
            )
            if res_full.returncode == 0:
                self.log_pass("Docker Compose (Full Profile)", "Full profile valid (postgres, ai-service, backend, frontend)")
            else:
                self.log_fail("Docker Compose (Full Profile)", f"Invalid syntax: {res_full.stderr.strip()}")
        except Exception as e:
            self.log_fail("Docker Compose (Full Profile)", f"Execution error: {e}")

        # 3c. Check companion-postgres container status
        try:
            res_ps = subprocess.run(
                ["docker", "ps", "--filter", "name=companion-postgres", "--format", "{{.Names}} - {{.Status}}"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=10,
            )
            status_out = res_ps.stdout.strip()
            if status_out and "companion-postgres" in status_out:
                self.log_pass("Container companion-postgres", f"Container is running ({status_out})")
            else:
                self.log_warn("Container companion-postgres", "companion-postgres is not running in local Docker engine")
        except Exception as e:
            self.log_warn("Container Inspection", f"Could not query docker ps: {e}")

    # -------------------------------------------------------------------------
    # 4. Telemetry & Observability Subsystem
    # -------------------------------------------------------------------------
    def check_telemetry(self):
        print(f"\n{BOLD}4. Verifying Telemetry & Observability Subsystem...{RESET}")
        try:
            from app.services.telemetry import TelemetryService

            ts = TelemetryService(max_traces=50)
            # Record synthetic test turn
            ts.record_turn(
                conversation_id="verify-conv-1",
                total_duration_ms=12.5,
                prompt_chars=40,
                response_chars=80,
                model="test-model",
                provider="test-provider",
                success=True,
            )
            # Record tool execution with secret arg to verify redaction
            ts.record_tool_execution(
                tool_name="read_file",
                arguments={"path": "app/main.py", "api_key": "SUPER_SECRET_VALUE"},
                duration_ms=5.0,
                success=True,
            )

            metrics = ts.get_metrics()
            traces = ts.get_traces()

            summary = metrics.get("summary", {})
            if summary.get("total_turns", 0) >= 1 and summary.get("total_tool_calls", 0) >= 1:
                self.log_pass("Telemetry Aggregation", f"Turns: {summary['total_turns']}, Tools: {summary['total_tool_calls']}")
            else:
                self.log_fail("Telemetry Aggregation", "Recorded telemetry events not reflected in metrics")

            if traces and "api_key" in traces[0]["arguments"]:
                if traces[0]["arguments"]["api_key"] == "[REDACTED]":
                    self.log_pass("Telemetry Secret Redaction", "api_key was safely sanitized to [REDACTED]")
                else:
                    self.log_fail("Telemetry Secret Redaction", "Secret leaked into trace buffer")
            else:
                self.log_fail("Telemetry Trace Inspection", "Could not verify trace arguments")

        except Exception as e:
            self.log_fail("Telemetry Subsystem", f"Exception raised: {type(e).__name__}: {e}")

    # -------------------------------------------------------------------------
    # 5. Live Service Health Probes
    # -------------------------------------------------------------------------
    def check_service_endpoints(self):
        print(f"\n{BOLD}5. Checking Service Health Endpoints...{RESET}")
        endpoints = [
            ("AI Service", "http://127.0.0.1:8000/api/health/"),
            ("Backend Gateway", "http://127.0.0.1:3001/api/health"),
            ("Frontend UI", "http://127.0.0.1:3000/api/health"),
        ]

        live_failures = 0
        for name, url in endpoints:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "StackVerifier/1.0"})
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    if resp.status in (200, 204):
                        self.log_pass(f"{name} Endpoint", f"ONLINE (status {resp.status}) at {url}")
                    else:
                        if self.require_live:
                            self.log_fail(f"{name} Endpoint", f"HTTP {resp.status} at {url}")
                            live_failures += 1
                        else:
                            self.log_warn(f"{name} Endpoint", f"HTTP {resp.status} at {url}")
            except urllib.error.URLError:
                if self.require_live:
                    self.log_fail(f"{name} Endpoint", f"OFFLINE at {url} (connection refused)")
                    live_failures += 1
                else:
                    self.log_info(f"{name} Endpoint", f"OFFLINE (ready for start via 'npm run dev' or docker) at {url}")
            except Exception as e:
                if self.require_live:
                    self.log_fail(f"{name} Endpoint", f"Error at {url}: {e}")
                    live_failures += 1
                else:
                    self.log_warn(f"{name} Endpoint", f"Probe error at {url}: {e}")

        return live_failures

    # -------------------------------------------------------------------------
    # Runner
    # -------------------------------------------------------------------------
    async def run(self) -> int:
        print(f"\n{BOLD}======================================================================{RESET}")
        print(f"{BOLD}    AI Software Engineering Companion — Stack Verification Script     {RESET}")
        print(f"{BOLD}======================================================================{RESET}")

        self.check_tool_registry()
        await self.check_database()
        self.check_docker_compose()
        self.check_telemetry()
        live_failures = self.check_service_endpoints()

        print(f"\n{BOLD}----------------------------------------------------------------------{RESET}")
        print(f"{BOLD}Verification Summary:{RESET}")
        print(f"  Passed checks:   {GREEN}{self.passed_count}{RESET}")
        print(f"  Warnings:        {YELLOW}{self.warn_count}{RESET}")
        print(f"  Failed checks:   {RED}{self.failed_count}{RESET}")

        if self.failed_count > 0:
            print(f"\n{RED}{BOLD}[RESULT: FAILED]{RESET} One or more required checks failed.")
            return 1

        if self.require_live and live_failures > 0:
            print(f"\n{RED}{BOLD}[RESULT: FAILED]{RESET} Live endpoints were required but {live_failures} were unreachable.")
            return 2

        print(f"\n{GREEN}{BOLD}[RESULT: PASSED]{RESET} All required stack checks succeeded!")
        return 0


def main():
    parser = argparse.ArgumentParser(description="AI Companion Full-Stack Verification")
    parser.add_argument("--require-live", action="store_true", help="Fail if live HTTP service endpoints are not running")
    parser.add_argument("--skip-db", action="store_true", help="Skip database connectivity verification")
    args = parser.parse_args()

    verifier = StackVerifier(require_live=args.require_live, skip_db=args.skip_db)
    exit_code = asyncio.run(verifier.run())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
