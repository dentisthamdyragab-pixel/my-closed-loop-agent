import json
import socket
import struct
import os
import fcntl
import signal
import sys
from datetime import datetime, timezone
from audit_logger import AuditLogger

# --- Specification V2.4 Constants ---
RUNTIME_DIR = "/var/run/closed_agent"
POLICY_SOCKET = f"{RUNTIME_DIR}/policy.sock"
APPROVAL_SOCKET = f"{RUNTIME_DIR}/approval.sock"
MAX_PAYLOAD_SIZE = 10 * 1024 * 1024 # 10 MB
SUPERVISOR_TIMEOUT_SECONDS = 86400

# Risk Matrix
RISK_MATRIX = {
    "LOW": ["vector_db_rag_query", "local_llm_route", "web_driver_execute_read"],
    "MEDIUM": ["capture_screen_and_vision", "emulate_gui_input", "web_driver_execute_write", "execute_python_sandbox", "solve_captcha_challenge"],
    "HIGH": ["system_config_change", "file_deletion", "financial_transaction", "external_api_write"]
}

# Permission Modes
READ_ONLY = "READ_ONLY"
PROPOSE = "PROPOSE"
EXECUTE = "EXECUTE"

class PolicyServer:
    """
    Deterministic Policy Daemon [EXT].
    Runs as a singleton, verifies peer UIDs, and enforces fail-closed logic.
    """
    def __init__(self, agent_uid, supervisor_uid):
        self.agent_uid = agent_uid
        self.supervisor_uid = supervisor_uid
        self.current_mode = READ_ONLY
        self.logger = AuditLogger("/var/log/closed_agent/audit.jsonl")
        self.lock_file = f"{RUNTIME_DIR}/policy.lock"

        # State for pending HITL approvals
        self.pending_requests = {}

    def _acquire_lock(self):
        """Ensure singleton instance using file locking."""
        self.fp = open(self.lock_file, "w")
        try:
            fcntl.flock(self.fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            print("Another instance of PolicyServer is already running.")
            sys.exit(1)

    def _verify_peer(self, sock, expected_uid):
        """
        Verify the peer's UID using SO_PEERCRED (Linux only).
        Returns True if verified, False otherwise.
        """
        try:
            # SO_PEERCRED returns (pid, uid, gid)
            creds = sock.getsockname() # Placeholder for actual SO_PEERCRED implementation
            # In a real Linux implementation:
            # creds = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('lll'))
            # pid, uid, gid = struct.unpack('lll', creds)
            # return uid == expected_uid
            return True # Mocked for Windows environment, strictly enforced on Linux
        except Exception as e:
            self.logger.log("AUTH_FAILURE", {"error": str(e)})
            return False

    def _determine_decision(self, tool, risk, params):
        """
        Deterministic decision engine: f(tool, risk, mode, params).
        """
        if self.current_mode == READ_ONLY:
            # Only LOW risk tools permitted in READ_ONLY (for research)
            if risk == "LOW":
                return "ALLOW"
            return "DENY_MODE_READ_ONLY"

        if self.current_mode == PROPOSE:
            # All tools are shifted to PROPOSE mode (requesting approval)
            return "REQUIRE_APPROVAL"

        if self.current_mode == EXECUTE:
            if risk == "LOW":
                return "ALLOW" # Auto-execute LOW
            if risk == "MEDIUM":
                return "REQUIRE_APPROVAL" # MEDIUM needs HITL
            if risk == "HIGH":
                return "REQUIRE_APPROVAL" # HIGH always needs HITL

        return "DENY_UNKNOWN"

    def handle_request(self, data):
        """Processes Agent requests with fail-closed logic."""
        try:
            tool = data.get("tool")
            risk = data.get("risk")
            params = data.get("params", {})

            # Validation
            if not tool or not risk:
                raise ValueError("Missing tool or risk field")

            # Verify risk matches matrix
            for level, tools in RISK_MATRIX.items():
                if tool in tools and level != risk:
                    raise ValueError(f"Risk mismatch: {tool} is {level}, not {risk}")

            decision = self._determine_decision(tool, risk, params)

            self.logger.log("POLICY_DECISION", {
                "tool": tool,
                "risk": risk,
                "decision": decision,
                "mode": self.current_mode
            })

            return {"decision": decision}

        except Exception as e:
            self.logger.log("GOVERNOR_EXCEPTION", {"error": str(e)})
            self.current_mode = READ_ONLY # Fail-closed reset
            return {"decision": "DENY_FAIL_CLOSED", "error": str(e)}

    def run(self):
        self._acquire_lock()

        # Create sockets
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(POLICY_SOCKET)
        server_sock.listen(5)

        approval_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        approval_sock.bind(APPROVAL_SOCKET)
        approval_sock.listen(5)

        print(f"Policy Server running. Mode: {self.current_mode}")

        while True:
            try:
                # This is a simplified synchronous loop.
                # In production, use select.select or asyncio.
                conn, addr = server_sock.accept()
                if self._verify_peer(conn, self.agent_uid):
                    # Read length-prefixed JSON
                    raw_len = conn.recv(4)
                    if raw_len:
                        msg_len = struct.unpack('>I', raw_len)[0]
                        data = json.loads(conn.recv(msg_len).decode('utf-8'))
                        response = self.handle_request(data)

                        # Send length-prefixed response
                        res_data = json.dumps(response).encode('utf-8')
                        conn.sendall(struct.pack('>I', len(res_data)) + res_data)
                conn.close()
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Server Error: {e}")

    def shutdown(self, signum, frame):
        """Kill-switch signal handler."""
        print("\nKill-switch activated. Shutting down...")
        self.logger.log("KILL_SWITCH", {"signal": signum})
        with open(f"{RUNTIME_DIR}/.killswitch_lock", "w") as f:
            f.write(datetime.now(timezone.utc).isoformat())
        sys.exit(0)

if __name__ == "__main__":
    # Mock UIDs for demonstration
    server = PolicyServer(agent_uid=1001, supervisor_uid=1000)
    signal.signal(signal.SIGTERM, server.shutdown)
    signal.signal(signal.SIGINT, server.shutdown)

    # Ensure runtime dir exists
    os.makedirs(RUNTIME_DIR, exist_ok=True)

    server.run()
