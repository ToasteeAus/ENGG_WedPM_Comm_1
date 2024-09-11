import socket
import json
from datetime import datetime, timezone

MCP_SERVER = ("10.20.30.177", 2000)
BUFFER_SIZE = 1024

# Datagram socket, used for UDP connection.
mcp_client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

def get_current_timestamp():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00Z')

current_action = "ON" # sets current action to on
CLIENT_ID = "BR28"

# Initialisation message for MCP
initialise = {
    "client_type": "ccp",
    "message": "CCIN",
    "client_id": CLIENT_ID,
    "timestamp": get_current_timestamp()
}

# Send message to MCP
mcp_client_socket.sendto(json.dumps(initialise).encode('utf-8'), MCP_SERVER)
print("Initialisation message sent to MCP.")

# Main loop to continuously listen for messages from MCP
while True:
    try:
        # Receive message from MCP
        msgFromMCP = mcp_client_socket.recvfrom(BUFFER_SIZE)
        decodedMessage = msgFromMCP[0].decode()
        
        # Parse JSON
        jsonData = json.loads(decodedMessage)
        if jsonData.get('client_id') == "BR28":  # Check if CLIENT_ID matches, only messages intended for BR28 are accepted.
            
            if jsonData['message'] == "AKIN":
                print(f"Received connection confirmation from MCP: {jsonData}")  # Debug statement. MCP connection successful.
            
            if jsonData['message'] == "STAT":
                print(f"Status request received.")  # Debug statement.
                status_msg = {
                    "client_type": "ccp",
                    "message": "STAT",
                    "client_id": "BR28",
                    "timestamp": get_current_timestamp(),
                    "status": current_action 
                }
                mcp_client_socket.sendto(json.dumps(status_msg).encode('utf-8'), MCP_SERVER)
                print(f"Sent status response to MCP: {status_msg}") # Debug statement

            elif jsonData['message'] == "EXEC":
                action = jsonData.get('action', '')
                print(f"Received EXEC command to perform action: {action}")
                
                # Accepted actions: "SLOW", "FAST", "STOP"
                if action in ["SLOW", "FAST", "STOP"]:
                    if current_action != action: # Updates current action of CCP. Used in sending status messages.
                        current_action = action
                        # TODO:
                        # Implement logic to send a command to the ESP32 to perform the blade runner operations.
                        # Needs to connect to ESP32 socket server over TCP.
                        print(f"Executing action: {action}\n")
                else:
                    print(f"Ignoring invalid EXEC action: {action}\n")

            elif jsonData['message'] == "DOOR":
                action = jsonData.get('action', '')
                print(f"Received DOOR command to perform action: {action}\n")
                
                # Accepted actions: "OPEN" and "CLOSE"
                if action in ["OPEN", "CLOSE"]:
                    if current_action != action:  
                        current_action = action
                        # TODO:
                        # Implement logic to send a command to the ESP32 to perform the blade runner operations.
                        # Needs to connect to ESP32 socket server over TCP.
                        print(f"Executing DOOR action: {action}\n")
                else:
                    print(f"Ignoring invalid DOOR action: {action}\n")
                
    except json.JSONDecodeError:
        print("Received a non-JSON message or malformed JSON.")
    except Exception as e:
        print(f"An error occurred: {e}")