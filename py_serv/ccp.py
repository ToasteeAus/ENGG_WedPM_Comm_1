import socket
import json
import time

# CCP Scope Variables

HOST = '0.0.0.0'  # Listen on all available interfaces
PORT = 12345       # Port to listen on

heartbeat_count = 0

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # create global-ish scoped socket to reference
client_socket = None

br_state = "OFF"
###########################################################

def heartbeat():
    global client_socket, heartbeat_count
    if client_socket is not None:
        data = {
            "heartbeat_count": heartbeat_count,
            "CMD":"SETUP"
        }
        
        json_data = json.dumps(data)
        
        client_socket.sendall(json_data.encode('utf-8'))
        print(f"Sent to client: {json_data}")
    
        heartbeat_count += 1

def echo():
    global client_socket
    if client_socket is not None:
        data = client_socket.recv(1024).decode('utf-8')
        if data:
            print(f"Received from client: {data}")

            # Send a response back to the client
            response = f"Echo: {data}"
            client_socket.sendall(response.encode('utf-8'))

def setup_esp_socket():
    # Bind the socket to the specified host and port
    global client_socket, server_socket
    server_socket.bind((HOST, PORT))

    server_ip = socket.gethostbyname(socket.gethostname())
    print(f"Server is hosting on IP address: {server_ip}:{PORT}")

    # Start listening for incoming connections (max 1 connection in the queue)
    server_socket.listen(1)

    print(f"Server listening for BR28 on {HOST}:{PORT}")
    # Accept a connection
    client_socket, client_address = server_socket.accept()
    print(f"Connection from {client_address}")
    
def setup_esp():
    global client_socket, br_state
    if client_socket is not None:
        sent_data = {
            "CMD":"SETUP"
        }
        
        sent_json_data = json.dumps(sent_data)
        
        client_socket.sendall(sent_json_data.encode('utf-8'))
        print(f"Sent to client: {sent_json_data}")
        
        # Receive back response from ESP32
        data = client_socket.recv(1024).decode('utf-8')
        
        if data:
            print(f"Received from client: {data}")

            # Attempt to parse the JSON data
            try:
                json_data = json.loads(data)
                
                print("Parsed JSON data:", json.dumps(json_data, indent=4))
                print(f"Returned Command: {json_data["CMD"]}")
            except json.JSONDecodeError:
                print("Failed to parse JSON")
        # Insert ACK of response
        # Confirm ACK back from ESP32
        # Change State
        br_state = "ON"
    
def status_esp():
    global client_socket
    if client_socket is not None:
        sent_data = {
            "CMD":"STATUS"
        }
        
        sent_json_data = json.dumps(sent_data)
        
        client_socket.sendall(sent_json_data.encode('utf-8'))
        print(f"Sent to client: {sent_json_data}")
        
        # Receive back response from ESP32
        data = client_socket.recv(1024).decode('utf-8')
        
        if data:
            print(f"Received from client: {data}")

            # Attempt to parse the JSON data
            try:
                json_data = json.loads(data)
                
                print("Parsed JSON data:", json.dumps(json_data, indent=4))
                print(f"Returned Status: {json_data["STATUS"]}")
            except json.JSONDecodeError:
                print("Failed to parse JSON")
        # Insert ACK of response
        # Confirm ACK back from ESP32
        
try:
    setup_esp_socket()
    
    while True:
        match br_state:
            case "OFF":
                setup_esp()
            case "ON":
                status_esp()
            case _:  
                heartbeat()
        time.sleep(1)

finally:
    # Close the connection with the client
    if client_socket is not None:
        client_socket.close()
    # Close the server socket
    server_socket.close()