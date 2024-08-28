import socket

IP = "127.0.0.1"
PORT = 20001

msgFromServer = "Connection to MCP successful."
bytesToSend = str.encode(msgFromServer) # Encode message.

# Datagram socket, used for UDP connection.
mcp_server_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

mcp_server_socket.bind((IP, PORT))

print("MCP test server running")

while True:
    bytesAddressPair = mcp_server_socket.recvfrom(1024)
    message = bytesAddressPair[0] # CCP message received on connection
    address = bytesAddressPair[1] # CCP IP address and Port

    decodedMessage = message.decode() # Decode message received from CCP

    clientMsg = "Message from CCP: {}".format(decodedMessage)
    clientIP = "CCP IP Address: {}".format(address)
    
    print(clientMsg)
    print(clientIP)

    # Send encoded message to CCP
    mcp_server_socket.sendto(bytesToSend, address)
