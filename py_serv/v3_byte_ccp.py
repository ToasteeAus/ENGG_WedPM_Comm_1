import socket, json, sys, time, logging, os, threading, queue, random
from datetime import datetime
from enum import Enum

# BladeRunner Commands
bladeRunnerCommands = {
    "STOP": "00",
    "FORWARD-SLOW": "01",
    "FORWARD-FAST": "02",
    "REVERSE-SLOW": "03",
    "REVERSE-FAST": "04",
    "DOORS-OPEN": "05",
    "DOORS-CLOSE": "06",
    "SET-SLOW-SPEED": "07",
    "SET-FAST-SPEED": "08",
    "DISCONNECT": "FF"
}
bladeRunnerCommandsKey_list = list(bladeRunnerCommands.keys())
bladeRunnerCommandsVal_list = list(bladeRunnerCommands.values())
BR_LAST_CMD = "00"

# Thread Safety Variable
RESTART_EXIT = False # Only to be set to True when we need to either RESTART or exit the system

# CCP_PORT ALLOCATION
CCP_PORT = 3028
BUFFER_SIZE = 1024
RECEIVE_ESP_BUFFER = 2
CLIENT_ID = "BR28"
JAVA_LINE_END = "\r\n"

# ESP Socket Server
CCP_TCP_SERVER = ('0.0.0.0', CCP_PORT)  # Listen on all available interfaces from CCP computer
esp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # create global-ish scoped socket to reference
esp_client_socket = None

# ESP Communication
ESP_SENT_Q = queue.Queue()
ESP_RECV_Q = queue.Queue() # ALL DATA IS ONLY HEX IN THE QUEUE
ESP_SENT_LOCK = threading.Lock()
ESP_RECV_LOCK = threading.Lock()

# MCP UDP Server
MCP_PORT = 3001
MCP_SERVER = ("10.20.30.193", MCP_PORT)
mcp_client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
MCP_CONNECTED = False

# MCP Communication
MCP_SENT_Q = queue.Queue()
MCP_RECV_Q = queue.Queue()
MCP_SENT_LOCK = threading.Lock()
MCP_RECV_LOCK = threading.Lock()

# MCP Specific Variables
BR_STATUS = ["STOPC", "STOPO", "FSLOWC", "FFASTC", "RSLOWC", "ERR", "OFLN"]
CURR_BR_STATUS = BR_STATUS[0]

MCP_CMDS = ["STOPC", "STOPO", "FSLOWC", "FFASTC", "RSLOWC", "DISCONNECT"]

MCP_MSG_REPLIES = {"EXEC":"AKEX",
                   "STRQ": "STAT"}

sequence_number = -1

BR_DOOR_OPEN = False # False for Closed, True for open
BR_CONNECTED = False # Used to flag for when our BR is attached and listening
CCIN_SENT = False # Used to flag for when our MCP Listener thread needs to actually start listening

# Unsorted Helpers

def get_sequence_number():
    global sequence_number
    # Here, s_ccp is a unique sequence number randomly chosen from the range 1000-30000,  
    # BRXX is the Blade Runner ID, and s_mcp is a unique sequence number randomly chosen from the range 1000-30000, 
    # and might not be the same value as s_ccp.
    
    if (sequence_number == -1):
        sequence_number = random.randint(1000, 30000)
        return sequence_number
    else:
        sequence_number = sequence_number + 1
        return sequence_number

def create_mcp_akex_msg():
    status_msg = {
                "client_type": "CCP",
                "message": "AKEX",
                "client_id": CLIENT_ID,
                "sequence_number": get_sequence_number()
            }
    
    print(status_msg)
    
    return status_msg

def create_mcp_stat_msg():
    status_msg = {
                "client_type": "CCP",
                "message": "STAT",
                "client_id": CLIENT_ID,
                "sequence_number": get_sequence_number(),
                "status": CURR_BR_STATUS
            }
    
    print(status_msg)
    
    return status_msg

# Logging

def setup_logging():
    if not os.path.exists("logs"):
        os.makedirs("logs")

    now = datetime.now()
    date_time = now.strftime("%d-%m-%Y_%H-%M-%S")
    log_file_name = "byte_ccp" + date_time + "_log.log"
    
        
    log_file_path = os.path.join("logs", log_file_name)
    logging.basicConfig(filename=log_file_path, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logging.info('Starting CCP Operations')
    print("Starting CCP Operations")

# ESP Socket Control

def setup_esp_socket():
    # Bind the socket to the specified host and port
    global esp_client_socket, esp_server_socket, BR_CONNECTED
    
    BR_CONNECTED = False
    esp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # reset global scoped references
    esp_client_socket = None
    
    esp_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    esp_server_socket.bind(CCP_TCP_SERVER)
    server_ip = socket.gethostbyname(socket.gethostname())
    
    # Start listening for incoming connections (max 1 connection in the queue)
    esp_server_socket.listen(1)
    logging.debug("ESP Socket listening")
    print("ESP Socket listening")
    print(f"Server listening for BR28 on {server_ip}:{CCP_PORT}")
    
    # Accept a connection -> HOLDS EXECUTION TIL ESP IS CONNECTED
    esp_client_socket, client_address = esp_server_socket.accept()
    logging.debug("ESP Socket attached")
    print("ESP Socket attached")
    BR_CONNECTED = True
    
    esp_client_socket.settimeout(15.0) # sets a 15 second timeout on any blocking action, this should hopefully cause our safety feature to kick in

def shutdown_esp_socket():
    # Close the connection with the client
    if esp_client_socket is not None:
        esp_client_socket.shutdown(socket.SHUT_RDWR)
        esp_client_socket.close()
    # Close the server socket
    esp_server_socket.close()

def send_esp_msg(data_to_send):
    global esp_client_socket, MCP_SENT_Q

    byte_data = bytes.fromhex(data_to_send)
    
    sent = False
    while sent == False:
        # TODO: Add in check if the SENT Queue is empty, if it is then we can send, otherwise hold cmd, only required if weird behaviour occurs
        if esp_client_socket is not None:
            try:
                esp_client_socket.sendall(byte_data)
                logging.debug(f"Sent to ESP: {data_to_send}")
                print(f"Sent to ESP: {data_to_send}")
                MCP_SENT_LOCK.acquire()
                MCP_SENT_Q.put(data_to_send)
                MCP_SENT_LOCK.release()
                sent = True
                
            except BrokenPipeError:
                logging.critical("ESP32 Connection Lost during transmission")
                print("ESP32 Connection Lost during transmission")
                setup_esp_socket()
        else:
            setup_esp_socket()
        # Behaviour should catch any case where for whatever reason the data cannot be transmitted n will attempt to startup the socket

def parse_esp_response():
    global ESP_RECV_Q, ESP_SENT_Q, bladeRunnerCommands, BR_DOOR_OPEN, BR_LAST_CMD, CURR_BR_STATUS
    
    if not ESP_RECV_Q.empty():
        ESP_RECV_LOCK.acquire()
        hex_data = ESP_RECV_Q.get()
        ESP_RECV_LOCK.release()
        
        if (len(hex_data) == 4):
            # we now have valid ack
            action = hex_data[:2]
            cmd = hex_data[2:]
            
            # Requirements to check ACK is valid, and for a valid command
            if (action == "aa"):
                try:
                    validCmd = bladeRunnerCommandsKey_list[bladeRunnerCommandsVal_list.index(cmd)] # Check the sent Ack Cmd exists in our list
                    
                    if (validCmd):
                        ESP_SENT_LOCK.acquire()
                        sentCmd = ESP_SENT_Q.get()
                        ESP_SENT_LOCK.release()
                        
                        logging.info(f"Received ACK from BR, sent: {sentCmd}, received: {cmd}")
                        print(f"Received ACK from BR, sent: {sentCmd}, received: {cmd}")
                        
                        BR_STATUS = ["STOPC", "STOPO", "FSLOWC", "FFASTC", "RSLOWC", "ERR"]
                        CURR_BR_STATUS = BR_STATUS[0]

                        match cmd:
                            case "00":
                                if BR_DOOR_OPEN:
                                    logging.debug("BR Successfully Stopped, Door Open")
                                    print("BR Successfully Stopped, Door Open")
                                    CURR_BR_STATUS = BR_STATUS[1]
                                    send_mcp_msg(create_mcp_stat_msg())
                                    # Send STOPO Status
                                else:
                                    logging.debug("BR Successfully Stopped, Door Closed")
                                    print("BR Successfully Stopped, Door Closed")
                                    CURR_BR_STATUS = BR_STATUS[0]
                                    send_mcp_msg(create_mcp_stat_msg())
                                    # Send STOPC Status
                            case "01":
                                if BR_DOOR_OPEN:
                                    logging.debug("BR Now moving Forward Slow with Door Open, ERR")
                                    print("BR Now moving Forward Slow with Door Open, ERR")
                                    CURR_BR_STATUS = BR_STATUS[5]
                                    send_mcp_msg(create_mcp_stat_msg())
                                else:
                                    logging.debug("BR Now Moving Forward Slow, searching for IR")
                                    print("BR Now Moving Forward Slow, searching for IR")
                                    CURR_BR_STATUS = BR_STATUS[2]
                                    send_mcp_msg(create_mcp_stat_msg())
                            case "02":
                                if BR_DOOR_OPEN:
                                    logging.debug("BR Now Moving Forward Fast with Door Open, ERR")
                                    print("BR Now Moving Forward Fast with Door Open, ERR")
                                    CURR_BR_STATUS = BR_STATUS[5]
                                    send_mcp_msg(create_mcp_stat_msg())
                                else:
                                    logging.debug("BR Now Moving Forward Fast")
                                    print("BR Now Moving Forward Fast")
                                    CURR_BR_STATUS = BR_STATUS[3]
                                    send_mcp_msg(create_mcp_stat_msg())
                            case "03":
                                if BR_DOOR_OPEN:
                                    logging.debug("BR Now Reversing Slow with Door Open, ERR")
                                    print("BR Now Reversing Slow with Door Open, ERR")
                                    CURR_BR_STATUS = BR_STATUS[5]
                                    send_mcp_msg(create_mcp_stat_msg())
                                else:
                                    logging.debug("BR Now Reversing Slow, searching for IR")
                                    print("BR Now Reversing Slow, searching for IR")
                                    CURR_BR_STATUS = BR_STATUS[4]
                                    send_mcp_msg(create_mcp_stat_msg())
                            case "04":
                                logging.debug("BR Now Reversing Fast, How did we get here...") # This shouldn't ever get called but eh
                                print("BR Now Reversing Fast, How did we get here...")
                                CURR_BR_STATUS = BR_STATUS[5]
                                send_mcp_msg(create_mcp_stat_msg())
                            case "05":
                                if BR_LAST_CMD == "00":
                                    logging.debug("BR Door now Open")
                                    print("BR Door now Open")
                                    CURR_BR_STATUS = BR_STATUS[1]
                                    send_mcp_msg(create_mcp_stat_msg())
                                else:
                                    logging.critical("BR Triggered Door Open State without Prior Stop state, ERR")
                                    print("BR Triggered Door Open State without Prior Stop state, ERR")
                                    CURR_BR_STATUS = BR_STATUS[5]
                                    send_mcp_msg(create_mcp_stat_msg())
                                    
                                BR_DOOR_OPEN = True 
                            case "06": # All other commands should ensure the door is shut
                                # Technically this can be called after any command but we'd prefer after a stop
                                if BR_LAST_CMD == "00":
                                    logging.debug("BR Door now Closed")
                                    print("BR Door now Closed")
                                    CURR_BR_STATUS = BR_STATUS[0]
                                    send_mcp_msg(create_mcp_stat_msg())
                                else:
                                    logging.critical("BR Triggered Door Closed State without Prior Stop state, ERR")
                                    print("BR Triggered Door Closed State without Prior Stop state, ERR")
                                    CURR_BR_STATUS = BR_STATUS[5]
                                    send_mcp_msg(create_mcp_stat_msg())
                                BR_DOOR_OPEN = False
                            case _:
                                logging.critical("BR has returned non-standard but valid command")
                                print("BR has returned non-standard but valid command")
                                CURR_BR_STATUS = BR_STATUS[5]
                                send_mcp_msg(create_mcp_stat_msg())
                            
                        BR_LAST_CMD = cmd
                except Exception as e:
                    logging.debug(e)
                    logging.debug(f"Received ACK from BR for unknown command: {cmd}")
                    print(e)
                    print(f"Received ACK from BR for unknown command: {cmd}")
                    
            elif (action == "ff"):
                # Now we have an ALERT from the ESP
                logging.debug(f"Received Alert from BR: {cmd}")
                if (cmd == "aa"):
                    logging.debug("BladeRunner aligned to station")
                    print("BladeRunner aligned to station")
                    CURR_BR_STATUS = BR_STATUS[0]
                    send_mcp_msg(create_mcp_stat_msg())
                    # Update status
                elif (cmd == "ab"):
                    logging.critical("BladeRunner has had collision!")
                    print("BladeRunner has had a collision!")
                    CURR_BR_STATUS = BR_STATUS[0]
                    send_mcp_msg(create_mcp_stat_msg())
                elif (cmd == "fe"):
                    logging.critical("BladeRUnner has lost power!")
                    print("BladeRunner has lost power!")
                    CURR_BR_STATUS = BR_STATUS[5]
                    send_mcp_msg(create_mcp_stat_msg())
                    
                elif (cmd == "ff"):
                    logging.critical("BladeRunner is now Offline")
                    print("BladeRunner is now Offline!")
                    CURR_BR_STATUS = BR_STATUS[6]
                    send_mcp_msg(create_mcp_stat_msg())
                
            else:
                logging.warning(f"Received non-valid action back from BR: {action}")
                print(f"Received non-valid action back from BR: {action}")
        else:
            logging.warning(f"Received malformed reply back from BR: {hex_data}")
            print(f"Received malformed reply back from BR: {hex_data}")

def esp_listener_thread():
    global ESP_RECV_Q, BR_CONNECTED
    
    while not RESTART_EXIT:
        data = ""
            
        try:
            data = esp_client_socket.recv(2)
            
            ESP_RECV_LOCK.acquire()
            ESP_RECV_Q.put(data.hex())
            ESP_RECV_LOCK.release()
        except TimeoutError:
            # it isn't always a guarantee that emptiness is confirmed by the queue, check again before we think its hit the fan
            logging.warning("ESP Socket Timeout")
            print("ESP Socket Timeout")
            continue
        except ConnectionResetError:
            # We have also lost the ESP but at a different phase
            logging.critical("ESP Socket Connection Reset")
            print("ESP Socket Connection Reset")
            BR_CONNECTED = False
            setup_esp_socket()
        except OSError:
            # Forcibly Exit
            logging.critical("ESP Socket Terminated")
            print("ESP Socket Terminated")
            break
        
        time.sleep(0.05)

# Master Control Program Interfacing

def send_mcp_msg(data_to_send): # expects a python dict obj to turn into a string
    success = False
    payload = json.dumps(data_to_send) + JAVA_LINE_END
    
    while success == False:
        try:
            if (mcp_client_socket.sendto(payload.encode('utf-8'), MCP_SERVER) > 0): # At least 1 byte has been sent, MCP is up
                success = True
                
                MCP_SENT_LOCK.acquire()
                MCP_SENT_Q.put(data_to_send)
                MCP_SENT_LOCK.release()
                
                logging.debug("Sent message to MCP: " + str(data_to_send))
        except OSError:
            logging.debug("MCP is not available, check IP or MCP Health status")
            # TODO: ADD FLAG TO INDICATE MCP CONNECTION IS SHODDY

def init_mcp_connection():
    global CCIN_SENT
    # Initialisation message for MCP
    init_json = {
        "client_type": "CCP",
        "message": "CCIN",
        "client_id": CLIENT_ID,
        "sequence_number": get_sequence_number()
    }
    
    # Send message to MCP
    send_mcp_msg(init_json)
    logging.debug("Initialisation message sent to MCP: " + str(init_json))
    print("Initialisation message sent to MCP: " + str(init_json))
    CCIN_SENT = True
    
    MCP_SENT_LOCK.acquire()
    MCP_SENT_Q.put(init_json)
    MCP_SENT_LOCK.release()

def parse_mcp_response():
    global MCP_CMDS, BR_DOOR_OPEN, MCP_RECV_Q, MCP_SENT_Q, ESP_SENT_Q, RESTART_EXIT
    
    if not MCP_RECV_Q.empty():
        MCP_RECV_LOCK.acquire()
        mcp_msg = MCP_RECV_Q.get()
        MCP_RECV_LOCK.release()
        
        if "STRQ" in mcp_msg["message"]:
            reply_msg = create_mcp_stat_msg()
            send_mcp_msg(reply_msg)
            # SEND reply_msg
        elif "EXEC" in mcp_msg["message"]:
            match mcp_msg["action"]:
                case "STOPC":
                    ESP_SENT_LOCK.acquire()
                    send_esp_msg(bladeRunnerCommands["STOP"])
                    ESP_SENT_Q.put(bladeRunnerCommands["STOP"])
                    
                    if BR_DOOR_OPEN:
                        send_esp_msg(bladeRunnerCommands["DOORS-CLOSE"])
                        ESP_SENT_Q.put(bladeRunnerCommands["DOORS-CLOSE"])
                        
                    ESP_SENT_LOCK.release()
                    
                    send_mcp_msg(create_mcp_akex_msg())
                        
                case "STOPO":
                    ESP_SENT_LOCK.acquire()
                    send_esp_msg(bladeRunnerCommands["STOP"])
                    ESP_SENT_Q.put(bladeRunnerCommands["STOP"])
                    
                    if not BR_DOOR_OPEN:
                        send_esp_msg(bladeRunnerCommands["DOORS-OPEN"])
                        ESP_SENT_Q.put(bladeRunnerCommands["DOORS-OPEN"])
                    ESP_SENT_LOCK.release()
                    
                    send_mcp_msg(create_mcp_akex_msg())
                        
                case "FSLOWC":
                    ESP_SENT_LOCK.acquire()
                    send_esp_msg(bladeRunnerCommands["FORWARD-SLOW"])
                    ESP_SENT_Q.put(bladeRunnerCommands["FORWARD-SLOW"])
                    
                    if BR_DOOR_OPEN:
                        send_esp_msg(bladeRunnerCommands["DOORS-CLOSE"])
                        ESP_SENT_Q.put(bladeRunnerCommands["DOORS-CLOSE"])
                    ESP_SENT_LOCK.release()
                    
                    send_mcp_msg(create_mcp_akex_msg())
                    
                case "FFASTC":
                    ESP_SENT_LOCK.acquire()
                    send_esp_msg(bladeRunnerCommands["FORWARD-FAST"])
                    ESP_SENT_Q.put(bladeRunnerCommands["FORWARD-FAST"])
                    
                    if BR_DOOR_OPEN:
                        send_esp_msg(bladeRunnerCommands["DOORS-CLOSE"])
                        ESP_SENT_Q.put(bladeRunnerCommands["DOORS-CLOSE"])
                    ESP_SENT_LOCK.release()
                    
                    send_mcp_msg(create_mcp_akex_msg())
                    
                case "RSLOWC":
                    ESP_SENT_LOCK.acquire()
                    send_esp_msg(bladeRunnerCommands["REVERSE-SLOW"])
                    ESP_SENT_Q.put(bladeRunnerCommands["REVERSE-SLOW"])
                    
                    if BR_DOOR_OPEN:
                        send_esp_msg(bladeRunnerCommands["DOORS-CLOSE"])
                        ESP_SENT_Q.put(bladeRunnerCommands["DOORS-CLOSE"])
                    ESP_SENT_LOCK.release()
                    
                    send_mcp_msg(create_mcp_akex_msg())
                    
                case "DISCONNECT": # When disconnecting we no longer shutdown, instead wait for BR to be removed and it will ping when shutting off
                    logging.critical("MCP Enforced Disconnect")
                    print("MCP Enforced Disconnect")
                    
                    ESP_SENT_LOCK.acquire()
                    send_esp_msg(bladeRunnerCommands["DISCONNECT"])
                    ESP_SENT_Q.put(bladeRunnerCommands["DISCONNECT"])
                    ESP_SENT_LOCK.release()
                    
                case _:
                    reply_msg = {
                        "client_type": "CCP",
                        "message": "NOIP",
                        "client_id": CLIENT_ID,
                        "sequence_number": get_sequence_number()}
                    send_mcp_msg(reply_msg)
                    logging.warning("Received NOIP command/message, sent reply")
                    print("Received NOIP command/message, sent reply")
                
        elif "AKST" in mcp_msg["message"]:
            MCP_SENT_LOCK.acquire()
            lastSent = MCP_SENT_Q.get()
            MCP_SENT_LOCK.release()
            
            logging.debug("Received AKST from our last STAT")
            print("Received AKST from our last STAT")
            
        elif "AKIN" in mcp_msg["message"]:
            MCP_SENT_LOCK.acquire()
            lastSent = MCP_SENT_Q.get()
            MCP_SENT_LOCK.release()
            
            logging.debug("Received AKIN, Awaiting MCP Commands")
            print("Received AKIN, Awaiting MCP Commands")
            
        else:
            reply_msg = {
                        "client_type": "CCP",
                        "message": "NOIP",
                        "client_id": CLIENT_ID,
                        "sequence_number": get_sequence_number()}
            
            send_mcp_msg(reply_msg)
            logging.warning("Received NOIP command/message, sent reply")
            print("Received NOIP command/message, sent reply")

def mcp_listener_thread():
    global CCIN_SENT
    
    while not RESTART_EXIT:
        if CCIN_SENT:
            data = ""
            
            try:
                data = mcp_client_socket.recvfrom(BUFFER_SIZE)[0].decode()
            except TimeoutError:
                # This means we've lost MCP, we need to re-init and stop our ESP
                CCIN_SENT = False
                # Send STOP command to BR
                logging.critical("MCP connection timed out")
                print("MCP connection timed out")

            except ConnectionResetError:
                # We've lost the MCP for some horrific error
                CCIN_SENT = False
                # Send STOP command to BR
                logging.critical("MCP connection reset")
                print("MCP connection reset")

            except OSError:
                # Forcibly Exit
                logging.critical("MCP UDP Socket Terminated")
                print("MCP UDP Socket Terminated")
                
            if data != "":
                return_data = ""
                logging.info(f"Received from MCP: {data}")
                print(f"Received from MCP: {data}")
                
                # Attempt to parse the JSON data 
                try:
                    return_data = json.loads(data)
                except json.JSONDecodeError:
                    logging.error("Received from MCP, but failed to parse JSON")
                    print("Received from MCP, but failed to parse JSON")
                    continue
                
                if return_data["client_id"] != CLIENT_ID or return_data["client_type"] != "CCP":
                    logging.error("Received from MCP, but incorrect client id or type")
                    print("Received from MCP, but incorrect client id or type")
                    continue
                
                # now we push return_data onto the queue
                MCP_RECV_LOCK.acquire()
                MCP_RECV_Q.put(return_data)
                MCP_RECV_LOCK.release()
        
        time.sleep(0.05)

# Core Processing

def core_processing():
    # TODO: Implement CCIN ping out until MCP is Connected!
    
    global CCIN_SENT, CURR_BR_STATUS
    while not RESTART_EXIT:
        if (not CCIN_SENT and BR_CONNECTED):
            init_mcp_connection()
            
        elif (CCIN_SENT and not BR_CONNECTED):
            CURR_BR_STATUS = BR_STATUS[5]
            send_mcp_msg(create_mcp_stat_msg())
            logging.critical("Logging with MCP that our BR has stopped Responding")
            print("Logging with MCP that our BR has stopped Responding")
            # This also means we are already attempting to restart our Bladerunner connection
        
        elif (CCIN_SENT and BR_CONNECTED):
            # Normal operation!
            parse_mcp_response()
            parse_esp_response()
                
        else:
            # This can only occur if our CCIN_SENT is False and BR_CONNECTED is False, let's re-assess if this is an even possible state
            logging.critical("Both our MCP connection and Bladerunner connection are down")
            print("Both our MCP connection and Bladerunner connection are down")
            
        time.sleep(0.05) # may need to add one line sleep per check for performance if it runs away from us
                
# System Initiation

def main_logic():
    setup_logging()
    setup_esp_socket()
    
    br_listener = threading.Thread(target=esp_listener_thread, args=())
    br_listener.daemon = True
    
    mcp_thread = threading.Thread(target=mcp_listener_thread, args=())
    mcp_thread.daemon = True
    
    br_listener.start()
    mcp_thread.start()
    
    core_processing()
        
    br_listener.join()
    mcp_thread.join()
    
if __name__ == '__main__':
    main_logic()