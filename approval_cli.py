import json
import socket
import struct
import sys

# Configuration
APPROVAL_SOCKET = "/var/run/closed_agent/approval.sock"

def send_approval(request_id, decision):
    """
    Sends an approval or rejection to the Policy Server.

    Args:
        request_id (str): ID of the pending request.
        decision (str): 'ALLOW' or 'REJECT'.
    """
    payload = {
        "request_id": request_id,
        "decision": decision
    }

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(APPROVAL_SOCKET)

            data = json.dumps(payload).encode('utf-8')
            s.sendall(struct.pack('>I', len(data)) + data)

            # Wait for confirmation
            raw_len = s.recv(4)
            if raw_len:
                msg_len = struct.unpack('>I', raw_len)[0]
                print(f"Server Response: {s.recv(msg_len).decode('utf-8')}")

    except Exception as e:
        print(f"Error sending approval: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python approval_cli.py <request_id> <ALLOW|REJECT>")
        sys.exit(1)

    req_id = sys.argv[1]
    decision = sys.argv[2].upper()
    if decision not in ["ALLOW", "REJECT"]:
        print("Invalid decision. Use ALLOW or REJECT.")
        sys.exit(1)

    send_approval(req_id, decision)
