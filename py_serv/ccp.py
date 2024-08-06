import socket
import time
import json

class ccp:
    JAVA_LINE_END = "\r\n"
    SETUP_MSG = "trainInit"
    POS = "0.1,"
    SPEED = "0.05"
    SAMPLE_MSG = "train,0.1,0.05"
    
    def __init__(self, port):
        self.port = port
        self.host = socket.gethostname()
        
        self.mcp_socket = socket.socket()
        self.mcp_socket.connect((self.host, self.port))
        print("Connected!")
        
    def setup_client(self):
        message = ccp.SETUP_MSG + ccp.JAVA_LINE_END
        self.mcp_socket.sendall(message.encode())
        
        data = self.mcp_socket.recv(1024).decode()
        print('Data received from MCP: ' + data)
        
    def send_info(self):
        message = ccp.SAMPLE_MSG + ccp.JAVA_LINE_END
        self.mcp_socket.sendall(message.encode())
        
        data = self.mcp_socket.recv(1024).decode()
        print('Data received from MCP: ' + data)
        
    def socket_listener(self):
        data = self.mcp_socket.recv(1024).decode()
        
        if data == "STATUS":
            message = "STATUS,0.2,0.05"

    def close_socket(self):
        self.mcp_socket.close()
    
    def main_logic(self):
        self.setup_client()
        time.sleep(3)
        self.send_info()
        time.sleep(5)
        self.close_socket()
        

if __name__ == '__main__':
    ccp = ccp(6666)
    ccp.main_logic()