'''
//  -------------------------------------------------------------
//  author        Giga
//  project       qeeqbox/honeypots
//  email         gigaqeeq@gmail.com
//  description   app.py (CLI)
//  licensee      AGPL-3.0
//  -------------------------------------------------------------
//  contributors list qeeqbox/honeypots/graphs/contributors
//  -------------------------------------------------------------
'''

from warnings import filterwarnings
filterwarnings(action='ignore', module='.*OpenSSL.*')

from socketserver import TCPServer, StreamRequestHandler, ThreadingMixIn
from struct import unpack
from os import path
from subprocess import Popen
from honeypots.helper import check_if_server_is_running, close_port_wrapper, get_free_port, kill_server_wrapper, server_arguments, set_local_vars, setup_logger
from uuid import uuid4


class QSOCKS5Server():
    def __init__(self, ip=None, port=None, username=None, password=None, mocking=False, config=''):
        self.auto_disabled = None
        self.mocking = mocking or ''
        self.process = None
        self.uuid = 'honeypotslogger' + '_' + __class__.__name__ + '_' + str(uuid4())[:8]
        self.ip = None
        self.port = None
        self.username = None
        self.password = None
        self.config = config
        if config:
            self.logs = setup_logger(self.uuid, config)
            set_local_vars(self, config)
        else:
            self.logs = setup_logger(self.uuid, None)
        self.ip = ip or self.ip or '0.0.0.0'
        self.port = port or self.port or 1080
        self.username = username or self.username or 'test'
        self.password = password or self.password or 'test'

    def socks5_server_main(self):
        _q_s = self

        class CustomStreamRequestHandler(StreamRequestHandler):

            def check_bytes(self, string):
                if isinstance(string, bytes):
                    return string.decode()
                else:
                    return str(string)

            def handle(self):
                _q_s.logs.info(['servers', {'server': 'socks5_server', 'action': 'connection', 'ip': self.client_address[0], 'port':self.client_address[1]}])
                v, m = unpack('!BB', self.connection.recv(2))
                if v == 5:
                    if 2 in unpack('!' + 'B' * m, self.connection.recv(m)):
                        self.connection.sendall(b'\x05\x02')
                        if 1 in unpack('B', self.connection.recv(1)):
                            _len = ord(self.connection.recv(1))
                            username = self.connection.recv(_len)
                            _len = ord(self.connection.recv(1))
                            password = self.connection.recv(_len)
                            username = self.check_bytes(username)
                            password = self.check_bytes(password)
                            status = 'failed'
                            if username == _q_s.username and password == _q_s.password:
                                username = _q_s.username
                                password = _q_s.password
                                status = 'success'
                            _q_s.logs.info(['servers', {'server': 'socks5_server', 'action': 'login', 'status': status, 'ip': self.client_address[0], 'port':self.client_address[1], 'username':username, 'password':password}])

                self.server.close_request(self.request)

        class ThreadingTCPServer(ThreadingMixIn, TCPServer):
            pass

        TCPServer.allow_reuse_address = True
        server = ThreadingTCPServer((self.ip, self.port), CustomStreamRequestHandler)
        server.serve_forever()

    def run_server(self, process=False, auto=False):
        if process:
            if self.close_port() and self.kill_server():
                self.process = Popen(['python3', path.realpath(__file__), '--custom', '--ip', str(self.ip), '--port', str(self.port), '--username', str(self.username), '--password', str(self.password), '--mocking', str(self.mocking), '--config', str(self.config), '--uuid', str(self.uuid)])
        else:
            self.socks5_server_main()

    def run_server(self, process=False, auto=False):
        status = 'error'
        run = False
        if process:
            if auto and not self.auto_disabled:
                port = get_free_port()
                if port > 0:
                    self.port = port
                    run = True
            elif self.close_port() and self.kill_server():
                run = True

            if run:
                self.process = Popen(['python3', path.realpath(__file__), '--custom', '--ip', str(self.ip), '--port', str(self.port), '--username', str(self.username), '--password', str(self.password), '--mocking', str(self.mocking), '--config', str(self.config), '--uuid', str(self.uuid)])
                if self.process.poll() is None and check_if_server_is_running(self.uuid):
                    status = 'success'

            self.logs.info(['servers', {'server': 'socks5_server', 'action': 'process', 'status': status, 'ip': self.ip, 'port': self.port, 'username': self.username, 'password': self.password}])

            if status == 'success':
                return True
            else:
                self.kill_server()
                return False
        else:
            self.socks5_server_main()

    def close_port(self):
        ret = close_port_wrapper('socks5_server', self.ip, self.port, self.logs)
        return ret

    def kill_server(self):
        ret = kill_server_wrapper('socks5_server', self.uuid, self.process)
        return ret


if __name__ == '__main__':
    parsed = server_arguments()
    if parsed.docker or parsed.aws or parsed.custom:
        QSOCKS5Server = QSOCKS5Server(ip=parsed.ip, port=parsed.port, username=parsed.username, password=parsed.password, mocking=parsed.mocking, config=parsed.config)
        QSOCKS5Server.run_server()
