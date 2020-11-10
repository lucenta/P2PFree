P2P Free
===================

A P2P based file synchronization program written in Python 3. The program uses a centralized server to facilitate file transfers. 

Run the server on the specified ip and port number:
```
python3 server.py <ip> <port>
```

Connect a client to the server:
```
python3 client.py <ip> <port>
```

Note that files will be synchronized in the directory of the client.py file. Folders will be ignored.
