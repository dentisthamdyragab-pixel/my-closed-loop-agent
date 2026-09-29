import json
import socket
import struct

class PolicyClient:
    """
    Framing-aware client for the Policy Server.
    Handles length-prefixed JSON communication.
    """
    def __init__(self, socket_path="/var/run/closed_agent/policy.sock"):
        self.socket_path = socket_path

    def request_permission(self, tool, risk, params=None):
        """
        Sends a permission request to the Policy Server.

        Args:
            tool (str): The tool name.
            risk (str): The risk level (LOW, MEDIUM, HIGH).
            params (dict): Parameters for the tool.

        Returns:
            dict: The server's decision.
        """
        if params is None:
            params = {}

        payload = {
            "tool": tool,
            "risk": risk,
            "params": params
        }

        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.connect(self.socket_path)

                # Send length-prefixed JSON
                data = json.dumps(payload).encode('utf-8')
                s.sendall(struct.pack('>I', len(data)) + data)

                # Read length-prefixed response
                raw_len = s.recv(4)
                if not raw_len:
                    return {"decision": "DENY_COMM_ERROR"}

                msg_len = struct.unpack('>I', raw_len)[0]
                response_data = s.recv(msg_len).decode('utf-8')
                return json.loads(response_data)

        except Exception as e:
            return {"decision": "DENY_CLIENT_ERROR", "error": str(e)}

if __name__ == "__main__":
    # Basic test
    client = PolicyClient()
    # Assuming server is running
    print("Testing LOW risk tool...")
    print(client.request_permission("vector_db_rag_query", "LOW"))

    print("\nTesting HIGH risk tool...")
    print(client.request_permission("system_config_change", "HIGH"))
