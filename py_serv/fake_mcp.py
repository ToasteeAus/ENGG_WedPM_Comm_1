import socket
import json

class mcp:
    
    
    def __init__(self, port):
        self.port = port
        self.host = socket.gethostname()
        
        self.mcp_socket = socket.socket()
        self.mcp_socket.bind((self.host, self.port))
    
        self.mcp_socket.listen(1) # In this perfect world we only need to communicate with 1 CCP
        self.ccp, self.ccp_address = self.mcp_socket.accept() # now we have found our CCP and we can use this to communicate back to it!
        print("Received CCP Connection from Address: " + str(self.ccp_address))
  
    def server(self):
        count = 0
        while True:
            # receive data stream. it won't accept data packet greater than 1024 bytes
            data = self.ccp.recv(1024).decode()
            
            if not data: break # nothing has come through the stream so eh
            
            print("From CCP: " + str(data))
            
            if (count == 0):
                data = json.dumps({"Temp":"True"})
                count += 1
            else:
                data = json.dumps({"Temp":"False"})
            
            self.ccp.send(bytes(data,encoding="utf-8"))  # send data to the client as utf8, json string moment

        self.ccp.close()  # close the connection
        
if __name__ == '__main__':
    main_mcp = mcp(5555)
    main_mcp.server()
    