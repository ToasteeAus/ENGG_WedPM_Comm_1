import socket, json, sys, time, logging, os
from datetime import datetime, timezone
from enum import Enum

# DEBUG FLAGS
DEBUG = True

# CCP_PORT ALLOCATION
CCP_PORT = 3028
BUFFER_SIZE = 1024
CLIENT_ID = "BR28"

# CCP States
BR_STATE = Enum('BR_STATE', ['CCP_OFFLINE','ESP_SETUP', 'THREADS_SETUP', 'MCP_SETUP', 'OPERATIONAL', 'ERROR', 'SHUTDOWN'])
ESP_STATE = Enum('ESP_STATE', ['ESP_OFFLINE', 'STOP', 'FORWARD_SLOW', 'FORWARD_FAST', 'REVERSE_SLOW', 'REVERSE_FAST', 'E_STOP', 'DOOR_OPEN', 'DOOR_CLOSE', 'COLLISION'])
CURR_BR_STATE = BR_STATE.CCP_OFFLINE
CURR_ESP_STATE = ESP_STATE.ESP_OFFLINE

# ESP Socket Server
CCP_TCP_SERVER = ('0.0.0.0', CCP_PORT)  # Listen on all available interfaces
esp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # create global-ish scoped socket to reference
esp_client_socket = None

# MCP UDP Server
MCP_PORT = 3001
MCP_SERVER = ("0.0.0.0", MCP_PORT)
mcp_client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

###########################################################
def get_current_timestamp():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00Z')

def set_br_state(new_state):
    global BR_STATE, CURR_BR_STATE
    CURR_BR_STATE = new_state
    logging.debug("Set CURR_BR_STATE to %s", CURR_BR_STATE)

def set_esp_state(new_state):
    global ESP_STATE, CURR_ESP_STATE
    CURR_ESP_STATE = new_state
    logging.debug("Set CURR_ESP_STATE to %s", CURR_ESP_STATE)

def send_esp_msg(data_to_send):
    global esp_client_socket, CURR_BR_STATE, CURR_ESP_STATE
    
    if esp_client_socket is not None:
        
        sent_json_data = json.dumps(data_to_send)
        try:
            esp_client_socket.sendall(sent_json_data.encode('utf-8'))
            logging.debug(f"Sent to client: {sent_json_data}")
        except BrokenPipeError:
            logging.critical("ESP32 Connection Lost during transmission")
            CURR_ESP_STATE = ESP_STATE.ESP_OFFLINE
            CURR_BR_STATE = BR_STATE.ERROR
            if DEBUG: setup_esp_socket()         

def recv_esp_msg():
    global CURR_ESP_STATE, CURR_BR_STATE
    # Receive back response from ESP32
    try:
        data = esp_client_socket.recv(BUFFER_SIZE).decode('utf-8') # for rev 1.0 we could implement a 4 byte size system ahead of json data
    except TimeoutError:
        # We've lost the ESP
        logging.critical("ESP connection timed out")
        CURR_ESP_STATE = ESP_STATE.ESP_OFFLINE
        CURR_BR_STATE = BR_STATE.ERROR
        if DEBUG: setup_esp_socket()
        return
    except ConnectionResetError:
        # We have also lost the ESP but at a different phase
        # My sincere hope is that we don't ever have to deal with an error like this in prod
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
    
    esp_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    esp_server_socket.bind(CCP_TCP_SERVER)
    server_ip = socket.gethostbyname(socket.gethostname())
    
    # Start listening for incoming connections (max 1 connection in the queue)
    esp_server_socket.listen(1)
    logging.debug("ESP Socket listening")
    if (CURR_BR_STATE == BR_STATE.SHUTDOWN or CURR_BR_STATE == BR_STATE.ERROR):
        if DEBUG: print("Lost connection to BR28")
        logging.warning("Attempting ESP re-connection")
        print(f"Attempting to reconnect to BR28 on {server_ip}:{CCP_PORT}")
    else: 
        print(f"Server listening for BR28 on {server_ip}:{CCP_PORT}")
    
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
    # Initialisation message for MCP
    init_json = {
        "client_type": "ccp",
        "message": "CCIN",
        "client_id": CLIENT_ID,
        "timestamp": get_current_timestamp()
    }
    
    # Send message to MCP
    mcp_client_socket.sendto(json.dumps(init_json).encode('utf-8'), MCP_SERVER)
    logging.info("Initialisation message sent to MCP.")
    
    mcp_ack = False
    
    while mcp_ack == False:
        recv_mcp_data = mcp_client_socket.recvfrom(BUFFER_SIZE)
        mcp_data_decoded = recv_mcp_data[0].decode()
        
        # Parse JSON
        json_data = json.loads(mcp_data_decoded)
        if json_data.get('client_id') == CLIENT_ID:  # Check if CLIENT_ID matches, only messages intended for BR28 are accepted.
            if json_data['message'] == "AKIN":
                logging.info("Received connection confirmation from MCP: %s", json_data)  # Debug statement. MCP connection successful.
                mcp_ack = True

    set_br_state(BR_STATE.OPERATIONAL)

def shutdown_esp_socket():
    # Close the connection with the client
    if esp_client_socket is not None:
        esp_client_socket.shutdown(socket.SHUT_RDWR)
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

def esp_forward_slow():
    setup_msg = {
        "CMD":"FORWARD_SLOW"
    }
    
    send_esp_msg(setup_msg)
    
    # Receive back response from ESP32
    data = recv_esp_msg()
    if data != None:
        if data["ACK"] == "FORWARD_SLOW_OK":
            logging.info("ESP is moving forward slow OK!")
            set_esp_state(ESP_STATE.FORWARD_SLOW)
        
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
            
def esp_reverse_fast():
    setup_msg = {
        "CMD":"REVERSE_FAST"
    }
    
    send_esp_msg(setup_msg)
    
    # Receive back response from ESP32
    data = recv_esp_msg()
    if data != None:
        if data["ACK"] == "REVERSE_FAST_OK":
            logging.info("ESP is reversing fast OK!")
            set_esp_state(ESP_STATE.REVERSE_FAST)
        
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
    if DEBUG:
        log_file_name = "test_" + date_time + "_log.log"
    else:
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

def mcp_status_creator():
    global CURR_BR_STATE, CURR_ESP_STATE
    # ESP_STATE = Enum('ESP_STATE', ['ESP_OFFLINE', 'STOP', 'FORWARD_SLOW', 'FORWARD_FAST', 'REVERSE_SLOW', 'REVERSE_FAST', 'E_STOP', 'DOOR_OPEN', 'DOOR_CLOSE', 'COLLISION'])

    status = ""
    match (CURR_BR_STATE):
        case BR_STATE.SHUTDOWN | BR_STATE.CCP_OFFLINE | BR_STATE.ESP_SETUP | BR_STATE.MCP_SETUP | BR_STATE.THREADS_SETUP:
            status = "OFF"
        case BR_STATE.OPERATIONAL:
            match (CURR_ESP_STATE):
                case ESP_STATE.ESP_OFFLINE:
                    status = "ERR"
                case ESP_STATE.STOP:
                    status = "STOPPED"
                case ESP_STATE.FORWARD_FAST | ESP_STATE.FORWARD_SLOW | ESP_STATE.REVERSE_FAST | ESP_STATE.REVERSE_SLOW:
                    status = "STARTED"
                case ESP_STATE.COLLISION:
                    status = "CRASH"
                case _:
                    status = "ON"
        case _:
            status = "ERR"

    status_msg = {
                "client_type": "ccp",
                "message": "STAT",
                "client_id": CLIENT_ID,
                "timestamp": get_current_timestamp(),
                "status": status 
            }
    
    return status_msg

def decode_mcp_request():
    test_client_id = 0
    returned_json_data = None
    
    while test_client_id != CLIENT_ID:
        recv_mcp_data = mcp_client_socket.recvfrom(BUFFER_SIZE)
        mcp_data_decoded = recv_mcp_data[0].decode()
        
        # Parse JSON
        json_data = json.loads(mcp_data_decoded)
        if json_data.get('client_id') == CLIENT_ID:  # Check if CLIENT_ID matches, only messages intended for BR28 are accepted.
            returned_json_data = json_data
            test_client_id = CLIENT_ID
    
    match (returned_json_data['message']):
        case "STAT":
            logging.debug("Status request received.")  # Debug statement.
            status_msg = mcp_status_creator()

            mcp_client_socket.sendto(json.dumps(status_msg).encode('utf-8'), MCP_SERVER)
            logging.info("Sent status response to MCP: %s", status_msg) # Debug statement
        case "EXEC":
            action = json_data.get('action', '')
            logging.debug("Received EXEC command to perform action: %s", action)
            
            match(action):
                case "SLOW":
                    esp_forward_slow()
                case "FAST":
                    esp_forward_fast()
                case "STOP":
                    esp_stop()
                case _:
                    logging.warning("Unknown EXEC command specified by MCP: %s", action)
        case "DOOR":
            action = json_data.get('action', '')
            logging.debug("Received EXEC command to perform action: %s", action)
            
            match(action):
                case "OPEN":
                    esp_door_open()
                case "CLOSE":
                    esp_door_close()
                case _:
                    logging.warning("Unknown DOOR command specified by MCP: %s", action)

def operational_logic():
    global CURR_BR_STATE
    # This will handle effectively all other ESP comms here and dealing with MCP
    # this will become the workhorse whilst our system is operational
    while CURR_BR_STATE == BR_STATE.OPERATIONAL:
        # Insert MCP communication handling here:
        # once communication has been dealt with, we will result with our stand-in for MCP command
        decode_mcp_request()

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
    
def remote_cli_test():
    # work through our state machine
    global CURR_BR_STATE, CURR_ESP_STATE
    setup_logging()
    logging.info("Started CLI Remote Test Session")
    print("Establishing the BladeRunner Command Line Interaction Tool v1")
    print("Copyright T5C1 @ 2024")
    print("Connection to BR28 being established")
    setup_esp_socket()
    set_br_state(BR_STATE.OPERATIONAL)
    
    while CURR_BR_STATE != BR_STATE.SHUTDOWN:
        human_control = input("br28> ").lower()
        match (human_control):
            case "quit" | "exit" | "q":
                # Behaviour note:
                # If attempting to quit in CLI mode, the program requires the ESP32 to be connected to safely disconnect, if it fails to do so,
                # the program will err and hang
                esp_stop()
                shutdown_esp_socket()
                sys.exit()
            case "forcequit" | "fq":
                # Behaviour note:
                # If the physical BladeRunner is not immobilised, it may continue to act on the last command without connection pending behaviour change
                # Only to be called if you do not care about the ESP being in a weird state
                confirm = input("NOTE: This command MAY leave the BladeRunner in a non-standard state.\nIt is the responsibility of the operator to ensure safety.\nNoting this, do you still wish to continue? (y/n) ")
                if confirm == "y" or confirm == "yes":
                    shutdown_esp_socket()
                    sys.exit()
            case "forward-fast" | "forwardfast" | "forward":
                esp_forward_fast()
            case "forward-slow" | "forwardslow":
                esp_forward_slow()
            case "reverse-fast" | "reversefast" | "reverse":
                esp_reverse_fast()
            case "reverse-slow" | "reverseslow":
                esp_reverse_slow()
            case "stop" | "e-stop":
                esp_stop()
            case "door-open":
                esp_door_open()
            case "door-close":
                esp_door_close()
            case "help" | "commands":
                print("List of available commands:\n")
                print("forward-fast:\nforwardfast:\nforward: -> move BladeRunner forwards, fast\n")
                print("forward-slow:\nforwardslow: -> move BladeRunner forwards, slow\n")
                print("reverse-fast:\nreversefast:\nreverse: -> move BladeRunner reverse, fast\n")
                print("forward-slow:\nforwardslow: -> move BladeRunner forwards, slow\n")
                print("stop:\ne-stop: -> stops BladeRunner\n")
                print("door-open: -> opens BladeRunner doors\n")
                print("door-close: -> closes BladeRunner doors\n")
                print("q:\nquit:\nexit: -> exits from BladeRunner Command Line Interaction Tool\n")
                print("fq:\nforcequit: -> forcefully exits from BladeRunner Command Line Interaction Tool\n[This command is unstable.]\n")
                print("help:\ncommands: -> lists all available commands from BladeRunner Command Line Interaction Tool")
            case _:
                print("Unknown command, available commands:\n")
                print("forward-fast:\nforwardfast:\nforward: -> move BladeRunner forwards, fast\n")
                print("forward-slow:\nforwardslow: -> move BladeRunner forwards, slow\n")
                print("reverse-fast:\nreversefast:\nreverse: -> move BladeRunner reverse, fast\n")
                print("forward-slow:\nforwardslow: -> move BladeRunner forwards, slow\n")
                print("stop:\ne-stop: -> stops BladeRunner\n")
                print("door-open: -> opens BladeRunner doors\n")
                print("door-close: -> closes BladeRunner doors\n")
                print("quit:\nexit: -> exits from BladeRunner Command Line Interaction Tool\n")
                print("fq:\nforcequit: -> forcefully exits from BladeRunner Command Line Interaction Tool\n[This command is unstable.]\n")
                print("help:\ncommands: -> lists all available commands from BladeRunner Command Line Interaction Tool")
    
    shutdown_esp_socket()
    
if __name__ == '__main__':
    if DEBUG:
        remote_cli_test()
    else:
        main_logic()