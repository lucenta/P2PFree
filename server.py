import socket, sys, threading, json, time, optparse, os, urllib.request

def validate_ip(s):
    a = s.split('.')
    if len(a) != 4:
        return False
    for x in a:
        if not x.isdigit():
            return False
        i = int(x)
        if i < 0 or i > 255:
            return False
    return True

def validate_port(x):
    if not x.isdigit():
        return False
    i = int(x)
    if i < 0 or i > 65535:
            return False
    return True

class Tracker(threading.Thread):
    def __init__(self, port, host):
        threading.Thread.__init__(self)
        self.BUFFER_SIZE = 8192
        self.port = port # Port used by tracker
        self.host = host # Tracker's IP address
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #socket to accept connections from peers
        self.users = [] # Track list if (ip, port #)
        self.files = {} # Track (ip, port, modified time) for each file
        self.lock = threading.Lock()
        try:
            self.server.bind((self.host, self.port)) # Bind to address and port
        except socket.error:
            print(('Bind failed %s' % (socket.error)))
            sys.exit()
        self.server.listen(1) #listen for connections

    # Delete user from self.users and their respective files 
    def delete_user(self, user):
        self.lock.acquire()
        print("Deleting user...")
        self.users.remove(user)
        filesToRemove = []
        for file in self.files:
            ID = (self.files[file]['ip'], self.files[file]['port'])
            if (ID == user):
                filesToRemove.append(file)
        # Remove files from self.files
        print("User ", user,", removed with files:")
        for i in filesToRemove:
            self.files.pop(i)
            print("\t",i)
        print("")
        print("Cur file status: \n ", self.files)
        self.lock.release()

    #Ensure sockets are closed on disconnect (This function is Not used)
    def exit(self):
        self.server.close()

    #Occurs when thread starts
    def run(self):
        print(('\n Waiting for connections on port %s ... \n' % (self.port)))
        while True:
            conn, addr = self.server.accept()
            threading.Thread(target=self.process_messages, args=(conn, addr)).start()

    #Receive file status of peer
    def process_messages(self, conn, addr):

        # Set userIP to machines IP if running server and tracker on same machine
        if (addr[0] == "127.0.0.1"):
            hostname = socket.gethostname()
            userIP = socket.gethostbyname(hostname)
        else:
            userIP = addr[0]
        print('Client connected with ' + userIP + ':' + str(addr[1]))
        while True:
            data = ''
            while True:
                part = conn.recv(self.BUFFER_SIZE).decode()
                if not part:
                    try:
                        print("")
                        print("User : ",userIP, ":", addr[1] ,", has disconnected.")
                        self.delete_user(user)
                        conn.close()
                        return
                    except UnboundLocalError:
                        print("Error in contacting user.\n")
                        conn.close() # Close sockets
                        return
                else:
                    data = data + part
                if len(part) < self.BUFFER_SIZE:
                    break
            try:
                json.loads(data)
            except ValueError:
                return

            data_dic = json.loads(data)         # deserialize
            user = (userIP, data_dic['port'])   # Store user 

            self.lock.acquire()
            if user not in self.users:
                self.users.append(user)
            self.lock.release()

            #Iterate through all files from a given user
            files = data_dic['files']
            for file in files:
                curfile = file['name']
                self.lock.acquire()
                if ((curfile not in self.files) or (file['mtime'] > self.files[curfile]['mtime'])):
                    self.files[curfile] = {'ip':userIP,'port':data_dic['port'],'mtime':int(file['mtime'])}
                self.lock.release()
            conn.send(bytes(json.dumps(self.files),'utf-8'))

if __name__ == '__main__':      
    parser = optparse.OptionParser(usage="%prog ServerIP ServerPort")
    options, args = parser.parse_args()
    if len(args) < 1:
        parser.error("No ServerIP and ServerPort")
    elif len(args) < 2:
        parser.error("No  ServerIP or ServerPort")
    else:
        if validate_ip(args[0]) and validate_port(args[1]):
            server_ip = args[0]
            server_port = int(args[1])
        else:
            parser.error("Invalid ServerIP or ServerPort")
    tracker = Tracker(server_port,server_ip)
    tracker.start()
