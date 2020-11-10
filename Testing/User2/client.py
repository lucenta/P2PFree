#!/usr/bin/env python3
import socket, sys, threading, json, time, os, ssl, os.path, glob, optparse, urllib.request, atexit

#Validate the IP address of the correct format
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

# Validate the port number is in range [0,2^16 -1 ]
def validate_port(x):
	if not x.isdigit():
		return False
	i = int(x)
	if i < 0 or i > 65535:
			return False
	return True

# Get file info in the local directory (subdirectories are ignored)
def get_file_info():
	files = []
	curPath = os.getcwd()
	for ob in os.listdir(curPath):
		if os.path.isfile(ob) and not(ob[0] == "." or ob[-3:] == ".py" or ob[-4:] == ".dll" or ob[-3:] == ".so" or ob[-8:] == ".command"):
			files.append({'name':ob , 'mtime': int(os.path.getmtime(ob))})
	return files
	
#Check if a port is available
def check_port_available(check_port):
	if str(check_port) in os.popen("netstat -na").read():
		return False
	return True

#Get the next available port by searching from initial_port to 2^16 - 1
def get_next_available_port(initial_port):
	maxPort = 65535
	curPort = initial_port
	while (curPort < maxPort):
		if (check_port_available(curPort) == True):
			return curPort
		else:
			curPort+=1
	return False

class FileSynchronizer(threading.Thread):
	def __init__(self,trackerhost,trackerport,port,host='0.0.0.0'):
		threading.Thread.__init__(self)
		atexit.register(self.exit_handler)
		self.BUFFER_SIZE = 8192		
		self.port = port # Port and host for serving file requests
		self.host = socket.gethostbyname(socket.gethostname())
		self.trackerhost = trackerhost # Tracker IP/hostname and port
		self.trackerport = trackerport
		self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Socket for tracker communication
		self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Socket for serving files
		self.msg = None
		#Create a TCP socket to serve file requests.
		try:
			self.server.bind((self.host, self.port))
		except socket.error:
			print(('Cannot connect to server %s' % (socket.error)))
			sys.exit()
		self.server.listen(10)

	# When crashing or closing perform this function
	def exit_handler(self):
		try:
			os.remove(self.fileToDelete)
		except TypeError: 
			pass
		self.server.close()
		self.client.close()
		print('Disonnecting...')

	# Handle file requests from a peer
	def process_message(self,conn,addr):
		try:
			filereq = conn.recv(self.BUFFER_SIZE).decode("utf-8")
			f = open(filereq,'rb')
			msg = f.read()
			f.close()
			conn.sendall(bytes(str(len(msg)), 'utf-8'))	# Send len of msg to peer
			print("length of file: ", len(msg))
			conn.recv(self.BUFFER_SIZE).decode("utf-8") # Receive ACK from peer
			conn.sendall(msg)
			conn.close()
			print("\t\t\t\tFile ", filereq, " send sucessfully.")
		except:
			print("Error in syncing, ",filereq," to ", addr[0], ":",addr[1] )
			conn.close()

	def run(self):
		self.client.connect((self.trackerhost,self.trackerport))
		t = threading.Timer(3, self.sync)
		t.start()
		print(('Waiting for connections on port %s' % (self.port)))
		while True:
			conn, addr = self.server.accept()
			threading.Thread(target=self.process_message, args=(conn,addr)).start()

	# Send updated file system to tracker and request necessary files
	def sync(self):
		curfiles = get_file_info() 
		self.msg = json.dumps({"port": self.port, "files": curfiles})
		self.client.send(bytes((self.msg),'utf-8'))
		directory_response_message = ''

		while True:
			part = self.client.recv(self.BUFFER_SIZE).decode()
			directory_response_message = directory_response_message + part
			if len(part) < self.BUFFER_SIZE:
				break

		try:
			data_dic = json.loads(directory_response_message)
		except json.decoder.JSONDecodeError:
			print("Tracker disconnected, exiting...") # If this happens, tracker has disconnected
			self.server.close()
			self.client.close()
			os._exit(1)

		# Create list to store current files. This makes it
		# easier to iterate through the names.
		filenames = []
		for file in curfiles:
			filenames.append(file['name'])

		# Store the names of the files that the peer does not have
		# into newFiles.
		newFiles = []
		for file in data_dic:
			if file not in filenames and not (data_dic[file]['ip'] == self.host and data_dic[file]['port'] == self.port):
				newFiles.append(file)

		# Store the names of the files that the peer must update 
		# into newFiles.
		for file in data_dic:
			for i in curfiles:
				if ((i['name'] == file and data_dic[file]['mtime'] > i['mtime'])):
					newFiles.append(file)

		# Remove any files that were deleted

		# Iterate through newFiles and request each file.
		for file in newFiles:
			try:
				print("\n\nGetting file: ",file, "...")
				f = open(file,"wb")
				clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
				clientSocket.connect((data_dic[file]['ip'],data_dic[file]['port']))
				clientSocket.send(bytes(file, 'utf-8'))
				fileSize = int(clientSocket.recv(self.BUFFER_SIZE).decode("utf-8"))
				clientSocket.sendall(bytes("a",'utf-8')) # Send ACK to peer
				bytesSent = 0
				while True:
					strng = clientSocket.recv(self.BUFFER_SIZE)
					bytesSent=bytesSent+len(strng)
					sys.stdout.write("\r%d%%" % ((bytesSent/fileSize)*100))
					sys.stdout.flush()
					if not strng:
						break
					f.write(strng)
				f.close()
				newFilesize = os.path.getsize(file)
				if (newFilesize < fileSize):
					print("")
					raise socket.error
				os.utime(file,(data_dic[file]['mtime'],data_dic[file]['mtime']))	# Change access time to pre-existing file time
				clientSocket.close()
				print("")
				print("File transfer successful")
			except socket.error:
				clientSocket.close()
				f.close()
				print("Error in getting file: ", file,". Client : ",data_dic[file]['ip'], ":", data_dic[file]['port']," was disconnected.")
				os.remove(file)

		t = threading.Timer(3, self.sync) #Step 5. start timer
		t.start()

if __name__ == '__main__':
	#parse command line arguments
	parser = optparse.OptionParser(usage="%prog ServerIP ServerPort")
	options, args = parser.parse_args()
	if len(args) < 1:
		parser.error("No ServerIP and ServerPort")
	elif len(args) < 2:
		parser.error("No  ServerIP or ServerPort")
	else:
		if validate_ip(args[0]) and validate_port(args[1]):
			tracker_ip = args[0]
			tracker_port = int(args[1])

		else:
			parser.error("Invalid ServerIP or ServerPort")
	#get free port
	synchronizer_port = get_next_available_port(10000)
	synchronizer_thread = FileSynchronizer(tracker_ip,tracker_port,synchronizer_port)
	synchronizer_thread.start()
