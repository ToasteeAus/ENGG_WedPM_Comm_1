import socket
import json
import time
from enum import Enum

# CCP Scope Variables
CCP_STATE = Enum('CCP_STATE', ['WAKE_UP', 'ESP_SETUP', 'MCP_INIT'])
CURR_STATE = CCP_STATE.WAKE_UP

HOST = '0.0.0.0'  # Listen on all available interfaces
PORT = 3028       # Port to listen on

esp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # create global-ish scoped socket to reference
esp_client_socket = None

###########################################################
def send_esp_msg(data_to_send):
    sent_json_data = json.dumps(data_to_send)
    
    esp_client_socket.sendall(sent_json_data.encode('utf-8'))
    print(f"Sent to client: {sent_json_data}")

def recv_esp_msg():
    # Receive back response from ESP32
    data = esp_client_socket.recv(1024).decode('utf-8')
    return_data = ""
    
    if data:
        print(f"Received from client: {data}")
        # Attempt to parse the JSON data
        
        try:
            json_data = json.loads(data)
            return_data = json.dumps(json_data)
            
            print(f"Returned Command: {json_data["CMD"]}")
            
        except json.JSONDecodeError:
            print("Received from client, but failed to parse JSON")
    
    return return_data

def setup_esp_socket():
    # Bind the socket to the specified host and port
    global esp_client_socket, esp_server_socket
    esp_server_socket.bind((HOST, PORT))
    server_ip = socket.gethostbyname(socket.gethostname())

    # Start listening for incoming connections (max 1 connection in the queue)
    esp_server_socket.listen(1)
    print(f"Server listening for BR28 on {server_ip}:{PORT}")
    
    # Accept a connection -> HOLDS EXECUTION TIL ESP IS CONNECTED
    esp_client_socket, client_address = esp_server_socket.accept()
    print(f"Connection from {client_address}")
    
def setup_esp():
    global esp_client_socket, CURR_STATE
    
    if esp_client_socket is not None:
        setup_msg = {
            "CMD":"SETUP"
        }
        
        send_esp_msg(setup_msg)
        
        # Receive back response from ESP32
        data = recv_esp_msg()
        
        if data["CMD"] == "SETUP_OK":
            CURR_STATE = CCP_STATE.ESP_SETUP
    else:
        CURR_STATE = CCP_STATE.WAKE_UP # Forces server to reconnect if failed before and jumped ahead
    
def status_esp():
    global esp_client_socket
    
    if esp_client_socket is not None:
        setup_msg = {
            "CMD":"SETUP"
        }
        
        send_esp_msg(setup_msg)
        
        # Receive back response from ESP32
        data = recv_esp_msg()
        
        if data["STATUS"] == "NORMINAL":
            print("ESP Working as expected!")
        
def mainLogic():
    # work through our state machine -> setup ESP for comms
    try: 
        while True:
            match CURR_STATE:
                case CCP_STATE.WAKE_UP:
                    setup_esp_socket()
                    setup_esp()
                case _:
                    print("We have defaulted here")
    finally:
        # Close the connection with the client
        if esp_client_socket is not None:
            esp_client_socket.close()
        # Close the server socket
        esp_server_socket.close()
    
if __name__ == '__main__':
    # Execute when the module is not initialized from an import statement.
    mainLogic()