import socket

# Define the host and port for the server
HOST = '0.0.0.0'  # Listen on all available interfaces
PORT = 12345       # Port to listen on

# Create a TCP socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Bind the socket to the specified host and port
server_socket.bind((HOST, PORT))

# Start listening for incoming connections (max 1 connection in the queue)
server_socket.listen(1)

print(f"Server listening on {HOST}:{PORT}")

# Accept a connection
client_socket, client_address = server_socket.accept()
print(f"Connection from {client_address}")

try:
    while True:
        # Receive data from the client
        data = client_socket.recv(1024).decode('utf-8')
        if not data:
            break
        print(f"Received from client: {data}")

        # Send a response back to the client
        response = f"Echo: {data}"
        client_socket.sendall(response.encode('utf-8'))

finally:
    # Close the connection with the client
    client_socket.close()

# Close the server socket
server_socket.close()