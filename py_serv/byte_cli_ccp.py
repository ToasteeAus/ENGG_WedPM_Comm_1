import socket, json, sys, time, logging, os, threading, queue
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
}

bladeRunnerCommandsKey_list = list(bladeRunnerCommands.keys())
bladeRunnerCommandsVal_list = list(bladeRunnerCommands.values())

# CLI Specific Info
CLI_INFO = False
HUMAN_INITIATED_EXIT = False

# CCP_PORT ALLOCATION
CCP_PORT = 3028
BUFFER_SIZE = 1024
RECEIVE_ESP_BUFFER = 2
CLIENT_ID = "BR28"

# ESP Socket Server
CCP_TCP_SERVER = ('0.0.0.0', CCP_PORT)  # Listen on all available interfaces from CCP computer
esp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # create global-ish scoped socket to reference
esp_client_socket = None

# Logging

def setup_logging():
    if not os.path.exists("logs"):
        os.makedirs("logs")

    now = datetime.now()
    date_time = now.strftime("%d-%m-%Y_%H-%M-%S")
    log_file_name = "byte_ccp" + date_time + "_log.log"
    
        
    log_file_path = os.path.join("logs", log_file_name)
    logging.basicConfig(filename=log_file_path, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logging.info('Starting CCP operations')

# ESP Socket Control

def setup_esp_socket():
    # Bind the socket to the specified host and port
    global esp_client_socket, esp_server_socket
    
    esp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # reset global scoped references
    esp_client_socket = None
    
    esp_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    esp_server_socket.bind(CCP_TCP_SERVER)
    server_ip = socket.gethostbyname(socket.gethostname())
    
    # Start listening for incoming connections (max 1 connection in the queue)
    esp_server_socket.listen(1)
    logging.debug("ESP Socket listening")

    print(f"Server listening for BR28 on {server_ip}:{CCP_PORT}")
    
    # Accept a connection -> HOLDS EXECUTION TIL ESP IS CONNECTED
    esp_client_socket, client_address = esp_server_socket.accept()
    logging.debug("ESP Socket attached")
    print(f"Connection from {client_address}")
    
    print("It is now safe to re-attempt commands: ")
    
    esp_client_socket.settimeout(15.0) # sets a 15 second timeout on any blocking action, this should hopefully cause our safety feature to kick in

def shutdown_esp_socket():
    # Close the connection with the client
    if esp_client_socket is not None:
        esp_client_socket.shutdown(socket.SHUT_RDWR)
        esp_client_socket.close()
    # Close the server socket
    esp_server_socket.close()

def send_esp_msg(data_to_send):
    global esp_client_socket

    byte_data = bytes.fromhex(data_to_send)
    
    sent = False
    while sent == False:
        if esp_client_socket is not None:
            try:
                esp_client_socket.sendall(byte_data)
                logging.debug(f"Sent to ESP: {data_to_send}")
                sent = True
                
            except BrokenPipeError:
                logging.critical("ESP32 Connection Lost during transmission")
                setup_esp_socket()
        else:
            setup_esp_socket()
        # Behaviour should catch any case where for whatever reason the data cannot be transmitted n will attempt to startup the socket

# BladeRunner Manual CLI

def remote_cli():
    global CLI_INFO, HUMAN_INITIATED_EXIT
    
    if CLI_INFO == False:
        logging.info("Started CLI Remote Test Session")
        print("Establishing the BladeRunner Command Line Interaction Tool v1")
        print("Copyright T5C1 @ 2024")
        print("Connection to BR28 being established")
        CLI_INFO = True
    
    while True:
        raw = input("br28> ").lower().split()
        
        if (len(raw) < 1): 
            continue
        
        human_control = raw[0]
        match (human_control):
            case "quit" | "exit" | "q":
                # Behaviour note:
                # If attempting to quit in CLI mode, the program requires the ESP32 to be connected to safely disconnect, if it fails to do so,
                # the program will err and hang
                send_esp_msg("FF")
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
                send_esp_msg(bladeRunnerCommands["FORWARD-FAST"])
            case "forward-slow" | "forwardslow":
                send_esp_msg(bladeRunnerCommands["FORWARD-SLOW"])
            case "reverse-fast" | "reversefast" | "reverse":
                send_esp_msg(bladeRunnerCommands["REVERSE-FAST"])
            case "reverse-slow" | "reverseslow":
                send_esp_msg(bladeRunnerCommands["REVERSE-SLOW"])
            case "stop" | "e-stop":
                send_esp_msg(bladeRunnerCommands["STOP"])
            case "set-slow-speed" | "setslow":
                if len(raw) == 2:
                    # Speed val
                    if(int(raw[1]) <= 255 and int(raw[1]) >= 0):
                        send_esp_msg(bladeRunnerCommands["SET-SLOW-SPEED"])
                        send_esp_msg(hex(int(raw[1])).removeprefix("0x"))
                    else:
                        print("The Speed command expects a speed value between 0 and 255\n")
                else:
                    print("The Speed command expects 1 whitespace separate speed value.\nex: setslow 9\n")
            case "set-fast-speed" | "setfast":
                if len(raw) == 2:
                    # Speed val
                    if(int(raw[1]) <= 255 and int(raw[1]) >= 0):
                        send_esp_msg(bladeRunnerCommands["SET-FAST-SPEED"])
                        send_esp_msg(hex(int(raw[1])).removeprefix("0x"))
                    else:
                        print("The Speed command expects a speed value between 0 and 255\n")
                else:
                    print("The Speed command expects 1 whitespace separate speed value.\nex: setfast 9\n")
            case "door-open":
                send_esp_msg(bladeRunnerCommands["DOORS-OPEN"])
            case "door-close":
                send_esp_msg(bladeRunnerCommands["DOORS-CLOSE"])
            case "help" | "commands":
                print("List of available commands:\n")
                print("forward-fast:\nforwardfast:\nforward: -> move BladeRunner forwards, fast\n")
                print("forward-slow:\nforwardslow: -> move BladeRunner forwards, slow\n")
                print("reverse-fast:\nreversefast:\nreverse: -> move BladeRunner reverse, fast\n")
                print("forward-slow:\nforwardslow: -> move BladeRunner forwards, slow\n")
                print("stop:\ne-stop: -> stops BladeRunner\n")
                print("set-fast-speed:\nsetfast: -> Set Fast Speed of the BladeRunner in operation\n")
                print("set-slow-speed:\nsetslow: -> Set Slow Speed of the BladeRunner in operation\n")
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

def esp_parser(hex_data):
    if (len(hex_data) == 4):
        # we now have valid ack
        action = hex_data[:2]
        cmd = hex_data[2:]
        
        # Requirements to check ACK is valid, and for a valid command
        if (action == "aa"):
            try:
                checkCmd = bladeRunnerCommandsKey_list[bladeRunnerCommandsVal_list.index(cmd)]
                if (checkCmd):
                    logging.debug(f"Received ACK from ESP: {checkCmd}")
            except:
                logging.debug(f"Received ACK from ESP for unknown command: {cmd}")
                
        elif (action == "ff"):
            # Now we have an ALERT from the ESP
            logging.debug(f"Received Alert from ESP: {cmd}")
            
        else:
            logging.warning(f"Received non-valid action back from ESP: {action}")
    else:
        logging.warning(f"Received malformed reply back from ESP: {hex_data}")

def esp_listener_thread():
    while not HUMAN_INITIATED_EXIT:
        data = ""      
        try:
            data = esp_client_socket.recv(2)
        except TimeoutError:
            # it isn't always a guarantee that emptiness is confirmed by the queue, check again before we think its hit the fan
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
            hex_data = data.hex()
            esp_parser(hex_data)

def main_logic():
    setup_logging()
    setup_esp_socket()
    
    thread1 = threading.Thread(target=esp_listener_thread, args=())
    thread1.daemon = True
    thread1.start()
    
    remote_cli()
    thread1.join()
    
if __name__ == '__main__':
    main_logic()