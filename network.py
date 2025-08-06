import socket

class Network:
    def __init__(self, is_server, host='127.0.0.1', port=12345):
        self.is_server = is_server
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if is_server:
            self.sock.bind((host, port))
            self.sock.listen(1)
            print(f"等待客户端连接({host}:{port})...")
            self.conn, _ = self.sock.accept()
            print("客户端已连接！")
        else:
            print(f"正在连接服务器({host}:{port})...")
            self.sock.connect((host, port))
            self.conn = self.sock
            print("已连接服务器！")

    def send(self, msg):
        self.conn.sendall((msg + '\n').encode())

    def recv(self):
        data = b''
        while not data.endswith(b'\n'):
            data += self.conn.recv(1024)
        return data.decode().strip()

    def close(self):
        self.conn.close()