# This file contains code to handle the UDP connection from MCP to CCP
import socket

msgFromClient = "Hello MCP! We control BR28"
bytesToSend = str.encode(msgFromClient) # Encode message.

serverAddressPort = ("127.0.0.1", 20001)

# Datagram socket, used for UDP connection.
ccp_client_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

ccp_client_socket.sendto(bytesToSend, serverAddressPort) # Send encoded message to MCP.

msgFromServer = ccp_client_socket.recvfrom(1024) # Message from MCP

decodedMessage = msgFromServer[0].decode() # Decode received message.

msg = "Message from MCP: {}".format(decodedMessage)

print(msg)


