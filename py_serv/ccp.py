import socket, json, sys, time, logging, os
from datetime import datetime
from enum import Enum

# CCP States
BR_STATE = Enum('BR_STATE', ['CCP_OFFLINE','ESP_SETUP', 'THREADS_SETUP', 'MCP_SETUP', 'OPERATIONAL', 'ERROR', 'SHUTDOWN'])
ESP_STATE = Enum('ESP_STATE', ['ESP_OFFLINE', 'STOP', 'FORWARD_SLOW', 'FORWARD_FAST', 'REVERSE_SLOW', 'REVERSE_FAST', 'E-STOP', 'DOOR_OPEN', 'DOOR_CLOSE', 'COLLISION'])
CURR_BR_STATE = BR_STATE.CCP_OFFLINE
CURR_ESP_STATE = ESP_STATE.ESP_OFFLINE

# ESP Socket Server
HOST = '0.0.0.0'  # Listen on all available interfaces
PORT = 3028       # Port to listen on

esp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # create global-ish scoped socket to reference
esp_client_socket = None

# MCP Socket Server
# filler for now


###########################################################
def set_br_state(new_state):
    global BR_STATE, CURR_BR_STATE
    CURR_BR_STATE = new_state
    logging.debug("Set CURR_BR_STATE to %s", CURR_BR_STATE)

def set_esp_state(new_state):
    global ESP_STATE, CURR_ESP_STATE
    CURR_ESP_STATE = new_state
    logging.debug("Set CURR_ESP_STATE to %s", CURR_ESP_STATE)

def send_esp_msg(data_to_send):
    global esp_client_socket
    
    if esp_client_socket is not None:
        
        sent_json_data = json.dumps(data_to_send)
        
        esp_client_socket.sendall(sent_json_data.encode('utf-8'))
        logging.debug(f"Sent to client: {sent_json_data}")

def recv_esp_msg():
    global CURR_ESP_STATE, CURR_BR_STATE
    # Receive back response from ESP32
    try:
        data = esp_client_socket.recv(1024).decode('utf-8') # for rev 1.0 we could implement a 4 byte size system ahead of json data
    except TimeoutError:
        logging.critical("ESP connection timed out")
        CURR_ESP_STATE = ESP_STATE.ESP_OFFLINE
        CURR_BR_STATE = BR_STATE.ERROR
        return
    
    return_data = ""
    
    if data:
        logging.info(f"Received from client: {data}")
        
        # Attempt to parse the JSON data 
        # TODO add in override code for if we receive a collision notice from the ESP to skip processing and jump to reporting
        try:
            return_data = json.loads(data)
        except json.JSONDecodeError:
            logging.error("Received from client, but failed to parse JSON")
    
    return return_data

def setup_esp_socket():
    # Bind the socket to the specified host and port
    global esp_client_socket, esp_server_socket, CURR_BR_STATE
    
    esp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # reset global scoped references
    esp_client_socket = None
    
    esp_server_socket.bind((HOST, PORT))
    server_ip = socket.gethostbyname(socket.gethostname())

    # Start listening for incoming connections (max 1 connection in the queue)
    esp_server_socket.listen(1)
    logging.debug("ESP Socket listening")
    if (CURR_BR_STATE == BR_STATE.SHUTDOWN):
        logging.warning("Attempting ESP re-connection")
        print(f"Attempting to reconnect to BR28 on {server_ip}:{PORT}")
    else: 
        print(f"Server listening for BR28 on {server_ip}:{PORT}")
    
    # Accept a connection -> HOLDS EXECUTION TIL ESP IS CONNECTED
    esp_client_socket, client_address = esp_server_socket.accept()
    logging.debug("ESP Socket attached")
    print(f"Connection from {client_address}")
    
    esp_client_socket.settimeout(10.0) # sets a 10 second timeout on any blocking action, this should hopefully cause our safety feature to kick in
    
    set_br_state(BR_STATE.ESP_SETUP) # Enter the next phase which is getting our ESP to check it's fully operational
    
def setup_esp():
    setup_msg = {
        "CMD":"SETUP"
    }
    
    send_esp_msg(setup_msg)
    
    # Receive back response from ESP32
    data = recv_esp_msg()
    if data != None:
        if data["ACK"] == "SETUP_OK":
            logging.info("ESP Setup OK!")
            set_br_state(BR_STATE.THREADS_SETUP)
            set_esp_state(ESP_STATE.STOP) # this should cause the ESP to enter the STOP state on the actual device
            # if the data returned is anything else, set state to BR_STATE.ERROR and await human intervention

def create_threads():
    logging.debug("Creating Threads Stub Reached")
    set_br_state(BR_STATE.MCP_SETUP)

def setup_mcp_socket():
    logging.debug("Setup MCP Socket Stub Reached")
    set_br_state(BR_STATE.OPERATIONAL)

def shutdown_esp_socket():
    # Close the connection with the client
    if esp_client_socket is not None:
        esp_client_socket.close()
    # Close the server socket
    esp_server_socket.close()
    set_br_state(BR_STATE.SHUTDOWN)

# ESP Commands

def esp_stop():
    setup_msg = {
        "CMD":"STOP"
    }
    
    send_esp_msg(setup_msg)
    
    # Receive back response from ESP32
    data = recv_esp_msg()
    
    if data != None:
        if data["ACK"] == "STOP_OK":
            logging.info("ESP Stopped OK!")
            set_esp_state(ESP_STATE.STOP)
        
def esp_forward_fast():
    setup_msg = {
        "CMD":"FORWARD_FAST"
    }
    
    send_esp_msg(setup_msg)
    
    # Receive back response from ESP32
    data = recv_esp_msg()
    if data != None:
        if data["ACK"] == "FORWARD_FAST_OK":
            logging.info("ESP is moving forward fast OK!")
            set_esp_state(ESP_STATE.FORWARD_FAST)
        
def esp_reverse_slow():
    setup_msg = {
        "CMD":"REVERSE_SLOW"
    }
    
    send_esp_msg(setup_msg)
    
    # Receive back response from ESP32
    data = recv_esp_msg()
    if data != None:
        if data["ACK"] == "REVERSE_SLOW_OK":
            logging.info("ESP is reversing slow OK!")
            set_esp_state(ESP_STATE.REVERSE_SLOW)
        
def esp_door_open():
    setup_msg = {
        "CMD":"DOOR_OPEN"
    }
    
    send_esp_msg(setup_msg)
    
    # Receive back response from ESP32
    data = recv_esp_msg()
    
    if data != None:
        if data["ACK"] == "DOOR_OPEN_OK":
            logging.info("ESP is opening doors OK!")
            set_esp_state(ESP_STATE.DOOR_OPEN)
        
def esp_door_close():
    setup_msg = {
        "CMD":"DOOR_CLOSE"
    }
    
    send_esp_msg(setup_msg)
    
    # Receive back response from ESP32
    data = recv_esp_msg()
    if data != None:
        if data["ACK"] == "DOOR_CLOSE_OK":
            logging.info("ESP is closing doors OK!")
            set_esp_state(ESP_STATE.DOOR_CLOSE)

# Core functions

def setup_logging():
    if not os.path.exists("logs"):
        os.makedirs("logs")

    now = datetime.now()
    date_time = now.strftime("%d-%m-%Y_%H-%M-%S")
    log_file_name = date_time + "_log.log"
    
        
    log_file_path = os.path.join("logs", log_file_name)
    
    logging.basicConfig(filename=log_file_path, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logging.info('Starting CCP operations')

def error_handler():
    global CURR_BR_STATE, CURR_ESP_STATE, esp_client_socket, esp_server_socket
    match (CURR_ESP_STATE):
        case ESP_STATE.ESP_OFFLINE:
            shutdown_esp_socket()
            setup_esp_socket()
            # by this point we should hopefully have our ESP back online
            CURR_BR_STATE = BR_STATE.OPERATIONAL # TODO recheck this code later as this will immediately trigger it to become operational again, we may need to disconnect from MCP in the case our ESP dies
        case _:
            print("This error is extraordinarily bad")
            sys.exit()

def operational_logic():
    global CURR_BR_STATE
    # This will handle effectively all other ESP comms here and dealing with MCP
    # this will become the workhorse whilst our system is operational
    curr_command = ESP_STATE.STOP
    while CURR_BR_STATE == BR_STATE.OPERATIONAL:
        # Insert MCP communication handling here:
        # once communication has been dealt with, we will result with our stand-in for MCP command
        match (curr_command):
            case ESP_STATE.STOP:
                esp_stop()
            case ESP_STATE.FORWARD_FAST:
                esp_forward_fast()
            case ESP_STATE.REVERSE_SLOW:
                esp_reverse_slow()
            case ESP_STATE.DOOR_OPEN:
                esp_door_open()
            case ESP_STATE.DOOR_CLOSE:
                esp_door_close()
            case _:
                logging.debug("reached default case within operational_logic")
        # this is not required in MVP but solely to test ESP comms
        curr_command_value = (curr_command.value + 1) % ESP_STATE.COLLISION.value + 1
        if curr_command_value == 0:
            curr_command = ESP_STATE.STOP
        else:
            curr_command = ESP_STATE(curr_command_value)

def main_logic():
    # work through our state machine
    global CURR_BR_STATE, CURR_ESP_STATE
    while CURR_BR_STATE != BR_STATE.SHUTDOWN:
        match (CURR_BR_STATE):
            case BR_STATE.CCP_OFFLINE:
                setup_logging()
                setup_esp_socket()
            case BR_STATE.ESP_SETUP:
                setup_esp()
            case BR_STATE.THREADS_SETUP:
                create_threads()
            case BR_STATE.MCP_SETUP:
                setup_mcp_socket()
            case BR_STATE.OPERATIONAL:
                operational_logic()
            case BR_STATE.ERROR:
                error_handler()
            case _:
                logging.debug("reached default case within main_logic")
    # in the case where we want to shutdown, we do it here
    shutdown_esp_socket()
    
if __name__ == '__main__':
    main_logic()