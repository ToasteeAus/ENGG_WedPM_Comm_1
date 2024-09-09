import socket, json, sys, time, logging, os, threading, queue
from datetime import datetime, timezone
from enum import Enum

# Debug Information
DEBUG = True
CLI_INFO = False
HUMAN_INITIATED_EXIT = False

# CCP_PORT ALLOCATION
CCP_PORT = 3028
BUFFER_SIZE = 1024
CLIENT_ID = "BR28"

# CCP States
SYS_STATE = Enum("SYS_STATE", ["OFFLINE", "ESP_CONNECTED", "MCP_CONNECTED"])
CURR_SYS_STATE = SYS_STATE.OFFLINE

ESP_ACTION = Enum("ESP_ACTION", ["STOP", "FORWARD_SLOW", 'FORWARD_FAST', 'REVERSE_SLOW', 'REVERSE_FAST', 'E_STOP', 'DOOR_OPEN', 'DOOR_CLOSE', 'COLLISION'])
CURR_ESP_ACTION = ESP_ACTION.STOP

ESP_STATUS = Enum("ESP_STATUS", ["STOPPED", "STARTED", "ON", "OFF", "ERR", "CRASH", "STOPPED_AT_STATION"])
CURR_ESP_STATUS = "OFF"

# ESP Socket Server
CCP_TCP_SERVER = ('0.0.0.0', CCP_PORT)  # Listen on all available interfaces
esp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # create global-ish scoped socket to reference
esp_client_socket = None

# ESP Communication
ESP_SENT_Q = queue.Queue()
ESP_RECV_Q = queue.Queue()
ESP_SENT_LOCK = threading.Lock()
ESP_RECV_LOCK = threading.Lock()

# Behaviour Note: If a thread has nothing to do (based on Queues being empty) the thread will sleep for 0.5s and check conditions again
# This *should* reduce the load on compute power when testing and in non-standard operation modes

# Logging
def setup_logging():
    if not os.path.exists("logs"):
        os.makedirs("logs")

    now = datetime.now()
    date_time = now.strftime("%d-%m-%Y_%H-%M-%S")
    if DEBUG:
        log_file_name = "test_multi_" + date_time + "_log.log"
    else:
        log_file_name = date_time + "_log.log"
    
        
    log_file_path = os.path.join("logs", log_file_name)
    logging.basicConfig(filename=log_file_path, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logging.info('Starting CCP operations')

# ESP Socket Control

def setup_esp_socket():
    # Bind the socket to the specified host and port
    global esp_client_socket, esp_server_socket, CURR_SYS_STATE
    
    esp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # reset global scoped references
    esp_client_socket = None
    
    esp_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    esp_server_socket.bind(CCP_TCP_SERVER)
    server_ip = socket.gethostbyname(socket.gethostname())
    
    # Start listening for incoming connections (max 1 connection in the queue)
    esp_server_socket.listen(1)
    logging.debug("ESP Socket listening")
    if (CURR_SYS_STATE != SYS_STATE.OFFLINE):
        # We should report an err to MCP here and then attempt to re-connect without blowing up the world
        # we should also confirm what state we were in, as either ESP or MCP have died
        
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
    
    set_sys_state(SYS_STATE.ESP_CONNECTED)

def shutdown_esp_socket():
    # Close the connection with the client
    if esp_client_socket is not None:
        esp_client_socket.shutdown(socket.SHUT_RDWR)
        esp_client_socket.close()
    # Close the server socket
    esp_server_socket.close()

def send_esp_msg(data_to_send):
    global esp_client_socket

    sent = False
    while sent == False:
        if esp_client_socket is not None:
            sent_json_data = json.dumps(data_to_send)
            
            try:
                esp_client_socket.sendall(sent_json_data.encode('utf-8'))
                logging.debug(f"Sent to client: {sent_json_data}")
                
                ESP_SENT_LOCK.acquire()
                ESP_SENT_Q.put(data_to_send)
                ESP_SENT_LOCK.release()
                
                sent = True
                
            except BrokenPipeError:
                logging.critical("ESP32 Connection Lost during transmission")
                setup_esp_socket()
        else:
            setup_esp_socket()
        # Behaviour should catch any case where for whatever reason the data cannot be transmitted n will attempt to startup the socket

# State/Status Helpers

def set_sys_state(new_state):
    global CURR_SYS_STATE
    CURR_SYS_STATE = new_state
    logging.debug("Set CURR_SYS_STATE to %s", CURR_SYS_STATE)

def set_esp_action(new_state):
    global CURR_ESP_ACTION
    CURR_ESP_ACTION = new_state
    logging.debug("Set CURR_ESP_ACTION to %s", CURR_ESP_ACTION)
    
def set_esp_status(new_state):
    global CURR_ESP_STATUS
    CURR_ESP_STATUS = new_state
    logging.debug("Set CURR_ESP_STATUS to %s", CURR_ESP_STATUS)

# ESP32 Commands

def setup_esp():
    setup_msg = {
        "CMD":"SETUP"
    }
    
    send_esp_msg(setup_msg)
    # Since we now have a guarantee from send_esp_msg of delivery, we can assume success
    set_sys_state(SYS_STATE.ESP_CONNECTED)
    set_esp_action(ESP_ACTION.STOP)
    set_esp_status(ESP_STATUS.STARTED)

def esp_stop():
    setup_msg = {
        "CMD":"STOP"
    }
    
    send_esp_msg(setup_msg)

    set_esp_action(ESP_ACTION.STOP)
    set_esp_status(ESP_STATUS.STOPPED)
        
def esp_forward_fast():
    setup_msg = {
        "CMD":"FORWARD_FAST"
    }
    
    send_esp_msg(setup_msg)
    
    set_esp_action(ESP_ACTION.FORWARD_FAST)
    set_esp_status(ESP_STATUS.ON)

def esp_forward_slow():
    setup_msg = {
        "CMD":"FORWARD_SLOW"
    }
    
    send_esp_msg(setup_msg)
    
    set_esp_action(ESP_ACTION.FORWARD_SLOW)
    set_esp_status(ESP_STATUS.ON)
        
def esp_reverse_slow():
    setup_msg = {
        "CMD":"REVERSE_SLOW"
    }
    
    send_esp_msg(setup_msg)
    
    set_esp_action(ESP_ACTION.REVERSE_SLOW)
    set_esp_status(ESP_STATUS.ON)
            
def esp_reverse_fast():
    setup_msg = {
        "CMD":"REVERSE_FAST"
    }
    
    send_esp_msg(setup_msg)
    
    set_esp_action(ESP_ACTION.REVERSE_FAST)
    set_esp_status(ESP_STATUS.ON)
        
def esp_door_open():
    setup_msg = {
        "CMD":"DOOR_OPEN"
    }
    
    send_esp_msg(setup_msg)
    
    set_esp_action(ESP_ACTION.DOOR_OPEN)
    set_esp_status(ESP_STATUS.STOPPED_AT_STATION)
        
def esp_door_close():
    setup_msg = {
        "CMD":"DOOR_CLOSE"
    }
    
    send_esp_msg(setup_msg)
    
    set_esp_action(ESP_ACTION.DOOR_CLOSE)
    set_esp_status(ESP_STATUS.STOPPED_AT_STATION)

# Core Thread Functions

def parse_esp_response():
    if not ESP_RECV_Q.empty():
        ESP_RECV_LOCK.acquire()
        esp_data = ESP_RECV_Q.get()
        ESP_RECV_LOCK.release()
        
        if "ACK" in esp_data:
            # We know at this point we're just handling a confirmation
            ESP_SENT_LOCK.acquire()
            ccp_data = ESP_SENT_Q.get()
            ESP_SENT_LOCK.release()
            
            expected_ack = ccp_data["CMD"] + "_OK"
            
            if esp_data["ACK"] == expected_ack:
                logging.info("ESP " + expected_ack + "!")
            else:
                logging.debug("Unexpected ESP ACK: " + esp_data["ACK"] + " when Expected: " + expected_ack)
        elif "ALERT" in esp_data:
            # We are now handling ESP generated alert which could be collision or station arrival
            #{"ALERT":"COLLISION"}
            #{"ALERT":"STOPPED_AT_STATION"}
            if esp_data["ALERT"] == "STOPPED_AT_STATION":
                # Send MSG to MCP (As we are on main messaging Thread!)
                logging.info("BladeRunner now at Station")
            elif esp_data["ALERT"] == "COLLISION":
                logging.info("BladeRunner collision occurred")
    else:
        return 0

# Threads

def remote_cli_test():
    global CLI_INFO, HUMAN_INITIATED_EXIT
    if CLI_INFO == False:
        logging.info("Started CLI Remote Test Session")
        print("Establishing the BladeRunner Command Line Interaction Tool v1")
        print("Copyright T5C1 @ 2024")
        print("Connection to BR28 being established")
        CLI_INFO = True
    
    while True:
        if ESP_RECV_Q.empty():
            human_control = input("br28> ").lower()
            match (human_control):
                case "quit" | "exit" | "q":
                    # Behaviour note:
                    # If attempting to quit in CLI mode, the program requires the ESP32 to be connected to safely disconnect, if it fails to do so,
                    # the program will err and hang
                    esp_stop()
                    shutdown_esp_socket()
                    HUMAN_INITIATED_EXIT = True
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
        else:
            time.sleep(0.25) # Slightly faaster for human-controlled operation

def esp_listener_thread():
    while not HUMAN_INITIATED_EXIT:
        if not ESP_SENT_Q.empty():
            data = ""
                    
            try:
                data = esp_client_socket.recv(BUFFER_SIZE).decode('utf-8')
            except TimeoutError:
                # it isn't always a guarantee that emptiness is confirmed by the queue, check again before we think its hit the fan
                if not ESP_SENT_Q.empty():
                    logging.critical("ESP connection timed out")
                    setup_esp_socket()
                else:
                    continue
                
            except ConnectionResetError:
                # We have also lost the ESP but at a different phase
                logging.critical("ESP connection reset")
                setup_esp_socket()
            
            except OSError:
                # Forcibly Exit
                logging.critical("ESP Socket Terminated")
                break
                
            if data != "":
                return_data = ""
                logging.info(f"Received from client: {data}")
                
                # Attempt to parse the JSON data 
                try:
                    return_data = json.loads(data)
                except json.JSONDecodeError:
                    logging.error("Received from client, but failed to parse JSON")
                
                # now we push return_data onto the queue
                ESP_RECV_LOCK.acquire()
                ESP_RECV_Q.put(return_data)
                ESP_RECV_LOCK.release()
        else:
            time.sleep(0.5)

def core_processing():
    global CURR_SYS_STATE
    while not HUMAN_INITIATED_EXIT:
        if CURR_SYS_STATE == SYS_STATE.OFFLINE:
            setup_esp()
        elif CURR_SYS_STATE == SYS_STATE.ESP_CONNECTED:
            if DEBUG and CLI_INFO == False: 
                cli_thread = threading.Thread(target=remote_cli_test, args=())
                cli_thread.daemon = True
                cli_thread.start()
            else:    
                pass
            # insert MCP Thread creation and CCIN code
            
        check = parse_esp_response()
        if(check == 0): time.sleep(0.5)
                        
def main_logic():
    setup_logging()
    setup_esp_socket()
                    
    thread1 = threading.Thread(target=esp_listener_thread, args=())
    thread1.daemon = True
    
    thread2 = threading.Thread(target=core_processing, args=())
    thread2.daemon = True
    
    thread1.start()
    thread2.start()
    
    thread1.join()
    thread2.join()

if __name__ == '__main__':
    main_logic()