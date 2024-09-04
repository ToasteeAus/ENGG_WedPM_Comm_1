import socket
import json
from datetime import datetime, timezone
import time
import threading

IP = "0.0.0.0"
PORT = 3001
BUFFER_SIZE = 1024

# Datagram socket, used for UDP connection.
mcp_server_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

mcp_server_socket.bind((IP, PORT))
server_ip = socket.gethostbyname(socket.gethostname())

print(f"MCP test server running on: {server_ip}:{PORT}")

client_id = None
ccp_initialised = False

def get_current_timestamp():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00Z')

def send_stat_requests():
    while True:
        if ccp_initialised:  # Only send STAT requests after CCP has initialised
            try:
                stat_request = {
                    "client_type": "ccp",  
                    "message": "STAT",
                    "client_id": client_id,
                    "timestamp": get_current_timestamp()
                }
                mcp_server_socket.sendto(json.dumps(stat_request).encode('utf-8'), ("127.0.0.1", 20002))
                print("STAT request sent to CCP")  # Debug statement
            except Exception as e:
                print(f"An error occurred while sending STAT request: {e}")
        time.sleep(2)  # status sent every 2 seconds as per requirement.

# Function to send EXEC commands.
def send_exec_commands():
    valid_actions = ["SLOW", "FAST", "STOP"]
    invalid_actions = ["JUMP", "RUN", "FLY"]

    if ccp_initialised:
        try:
            for action in valid_actions + invalid_actions:
                exec_command = {
                    "client_type": "ccp",
                    "message": "EXEC",
                    "client_id": client_id,
                    "action": action,
                    "timestamp": get_current_timestamp()
                }
                mcp_server_socket.sendto(json.dumps(exec_command).encode('utf-8'), ("127.0.0.1", 20002))
                print(f"Sent EXEC command to CCP: {exec_command}")
                time.sleep(2)
        except Exception as e:
            print(f"An error occurred while sending EXEC command: {e}")

# Function to send DOOR commands.
def send_door_commands():
    valid_actions = ["OPEN", "CLOSE"]
    invalid_actions = ["LOCK", "UNLOCK"]

    if ccp_initialised:
        try:
            for action in valid_actions + invalid_actions:
                door_command = {
                    "client_type": "ccp",
                    "message": "DOOR",
                    "client_id": client_id,
                    "action": action,
                    "timestamp": get_current_timestamp()
                }
                mcp_server_socket.sendto(json.dumps(door_command).encode('utf-8'), ("127.0.0.1", 20002))
                print(f"Sent DOOR command to CCP: {door_command}")
                time.sleep(2)  # 3-second delay between each command
        except Exception as e:
            print(f"An error occurred while sending DOOR command: {e}")

# Function to send a command to a different client_id for testing. 
def incorrect_client_id():
    if ccp_initialised:
        try:
            false_exec = {
                "client_type": "ccp",
                "message": "EXEC",
                "client_id": "BR29",  # Different client_id for testing
                "action": "FAST",
                "timestamp": get_current_timestamp()
            }
            mcp_server_socket.sendto(json.dumps(false_exec).encode('utf-8'), ("127.0.0.1", 20002))
            print(f"Sent EXEC command to different client_id (BR29): {false_exec}\n")
        except Exception as e:
            print(f"An error occurred while sending command to different client_id: {e}")

def execute_commands():
    while not ccp_initialised:
        time.sleep(1)  # Check every second if CCP has been initialised (loops until you connect to MCP from CCP)
    send_exec_commands()
    send_door_commands()
    incorrect_client_id()

# STATUS: Start a separate thread to handle periodic STAT requests
stat_thread = threading.Thread(target=send_stat_requests)
stat_thread.daemon = True  # thread exits when the main program exits
stat_thread.start()

# COMMANDS: Start a thread to send EXEC and DOOR commands sequentially after CCP has initialised
commands_thread = threading.Thread(target=execute_commands)
commands_thread.daemon = True
commands_thread.start()

# Main loop to continuously listen for messages from CCP
while True:
    try:
        # Receive incoming message from CCP
        bytesAddressPair = mcp_server_socket.recvfrom(BUFFER_SIZE)
        message = bytesAddressPair[0]  # CCP message received on connection
        address = bytesAddressPair[1]  # CCP IP address and Port

        decodedMessage = message.decode()  # Decode message received from CCP

        # Parse the incoming message as JSON
        jsonData = json.loads(decodedMessage)
        print(f"Message from CCP: {jsonData}")
        
        if jsonData['message'] == "CCIN":
            ccp_initialised = True
            client_id = jsonData['client_id']
            print("CCP initialised. Sending AKIN response.")

            # Send AKIN response to CCP to acknowledge initialisation
            akin_response = {
                "client_type": "ccp",
                "message": "AKIN",
                "client_id": client_id,
                "timestamp": get_current_timestamp()
            }
            mcp_server_socket.sendto(json.dumps(akin_response).encode('utf-8'), address)
            print("AKIN response sent.")
                        
        elif jsonData['message'] == "STAT":
            if ccp_initialised:  # Check if CCP has been initialised
                if 'status' in jsonData:
                    print(f"Status response from CCP: {jsonData['status']}")
                else:
                    print("Status response received but 'status' field is missing.")

    except json.JSONDecodeError:
        print("Received a non-JSON message or malformed JSON.")
    
    except Exception as e:
        print(f"An error occurred: {e}")
