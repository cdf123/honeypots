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

from twisted.internet.protocol import Protocol, Factory
from twisted.internet import reactor
from struct import unpack
from twisted.python import log as tlog
from subprocess import Popen
from os import path
from honeypots.helper import close_port_wrapper, get_free_port, kill_server_wrapper, server_arguments, setup_logger, disable_logger, set_local_vars, check_if_server_is_running
from uuid import uuid4


class QPostgresServer():
    def __init__(self, ip=None, port=None, username=None, password=None, mocking=False, config=''):
        self.auto_disabled = None
        self.mocking = mocking or ''
        self.process = None
        self.uuid = 'honeypotslogger' + '_' + __class__.__name__ + '_' + str(uuid4())[:8]
        self.config = config
        self.ip = None
        self.port = None
        self.username = None
        self.password = None
        if config:
            self.logs = setup_logger(self.uuid, config)
            set_local_vars(self, config)
        else:
            self.logs = setup_logger(self.uuid, None)
        self.ip = ip or self.ip or '0.0.0.0'
        self.port = port or self.port or 5432
        self.username = username or self.username or 'test'
        self.password = password or self.password or 'test'
        disable_logger(1, tlog)

    def postgres_server_main(self):
        _q_s = self

        class CustomPostgresProtocol(Protocol):

            _state = None
            _variables = {}

            def check_bytes(self, string):
                if isinstance(string, bytes):
                    return string.decode()
                else:
                    return str(string)

            def read_data_custom(self, data):
                _data = data.decode('utf-8')
                length = unpack('!I', data[0:4])
                encoded_list = (_data[8:-1].split('\x00'))
                self._variables = dict(zip(*([iter(encoded_list)] * 2)))

            def read_password_custom(self, data):
                data = data.decode('utf-8')
                self._variables['password'] = data[5:].split('\x00')[0]

            def connectionMade(self):
                self._state = 1
                self._variables = {}
                _q_s.logs.info(['servers', {'server': 'postgres_server', 'action': 'connection', 'ip': self.transport.getPeer().host, 'port': self.transport.getPeer().port}])

            def dataReceived(self, data):
                if self._state == 1:
                    self._state = 2
                    self.transport.write(b'N')
                elif self._state == 2:
                    self.read_data_custom(data)
                    self._state = 3
                    self.transport.write(b'R\x00\x00\x00\x08\x00\x00\x00\x03')
                elif self._state == 3:
                    if data[0] == 112 and 'user' in self._variables:
                        self.read_password_custom(data)
                        username = self.check_bytes(self._variables['user'])
                        password = self.check_bytes(self._variables['password'])
                        status = 'failed'
                        if username == _q_s.username and password == _q_s.password:
                            username = _q_s.username
                            password = _q_s.password
                            status = 'success'
                        _q_s.logs.info(['servers', {'server': 'postgres_server', 'action': 'login', 'status': status, 'ip': self.transport.getPeer().host, 'port': self.transport.getPeer().port, 'username': username, 'password': password}])

                    self.transport.loseConnection()
                else:
                    self.transport.loseConnection()

            def connectionLost(self, reason):
                self._state = 1
                self._variables = {}

        factory = Factory()
        factory.protocol = CustomPostgresProtocol
        reactor.listenTCP(port=self.port, factory=factory, interface=self.ip)
        reactor.run()

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

            self.logs.info(['servers', {'server': 'postgres_server', 'action': 'process', 'status': status, 'ip': self.ip, 'port': self.port, 'username': self.username, 'password': self.password}])

            if status == 'success':
                return True
            else:
                self.kill_server()
                return False
        else:
            self.postgres_server_main()

    def close_port(self):
        ret = close_port_wrapper('postgres_server', self.ip, self.port, self.logs)
        return ret

    def kill_server(self):
        ret = kill_server_wrapper('postgres_server', self.uuid, self.process)
        return ret


if __name__ == '__main__':
    parsed = server_arguments()
    if parsed.docker or parsed.aws or parsed.custom:
        qpostgresserver = QPostgresServer(ip=parsed.ip, port=parsed.port, username=parsed.username, password=parsed.password, mocking=parsed.mocking, config=parsed.config)
        qpostgresserver.run_server()
