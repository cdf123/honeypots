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
from Crypto.Cipher import DES
from binascii import unhexlify
from twisted.python import log as tlog
from subprocess import Popen
from os import path
#from vncdotool import api as vncapi
from honeypots.helper import close_port_wrapper, get_free_port, kill_server_wrapper, server_arguments, setup_logger, disable_logger, set_local_vars, check_if_server_is_running
from uuid import uuid4


class QVNCServer():
    def __init__(self, ip=None, port=None, username=None, password=None, mocking=False, dict_=None, config=''):
        self.auto_disabled = None
        self.mocking = mocking or ''
        self.random_servers = ['VNC Server']
        self.file_name = dict_ or None
        self.challenge = unhexlify('00000000901234567890123456789012')
        if not dict_:
            self.words = ['test']
        else:
            self.load_words()
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
        self.port = port or self.port or 5900
        self.username = username or self.username or 'test'
        self.password = password or self.password or 'test'
        disable_logger(1, tlog)

    def load_words(self,):
        with open(self.file_name, 'r') as file:
            self.words = file.read().splitlines()

    def decode(self, c, r):
        try:
            for word in self.words:
                temp = word
                word = word.strip('\n').ljust(8, '\00')[:8]
                rev_word = []
                for i in range(0, 8):
                    rev_word.append(chr(int('{:08b}'.format(ord(word[i]))[::-1], 2)))
                output = DES.new(''.join(rev_word).encode('utf-8'), DES.MODE_ECB).encrypt(c)
                if output == r:
                    return temp
        except BaseException:
            pass

        return None

    def vnc_server_main(self):
        _q_s = self

        class CustomVNCProtocol(Protocol):

            _state = None

            def check_bytes(self, string):
                if isinstance(string, bytes):
                    return string.decode()
                else:
                    return str(string)

            def connectionMade(self):
                self.transport.write(b'RFB 003.008\n')
                self._state = 1
                _q_s.logs.info(['servers', {'server': 'vnc_server', 'action': 'connection', 'ip': self.transport.getPeer().host, 'port': self.transport.getPeer().port}])

            def dataReceived(self, data):
                if self._state == 1:
                    if data == b'RFB 003.008\n':
                        self._state = 2
                        self.transport.write(unhexlify('0102'))
                elif self._state == 2:
                    if data == b'\x02':
                        self._state = 3
                        self.transport.write(_q_s.challenge)
                elif self._state == 3:
                    try:
                        username = self.check_bytes(_q_s.decode(_q_s.challenge, data.hex()))
                        password = self.check_bytes(data)
                        status = 'failed'
                        # may need decode
                        if username == _q_s.username and password == _q_s.password:
                            username = _q_s.username
                            password = _q_s.password
                            status = 'success'
                        else:
                            password = data.hex()
                        _q_s.logs.info(['servers', {'server': 'vnc_server', 'action': 'login', status: 'failed', 'ip': self.transport.getPeer().host, 'port': self.transport.getPeer().port, 'username': username, 'password': password}])
                    except Exception as e:
                        print(e)
                    self.transport.loseConnection()
                else:
                    self.transport.loseConnection()

            def connectionLost(self, reason):
                self._state = None

        factory = Factory()
        factory.protocol = CustomVNCProtocol
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

            self.logs.info(['servers', {'server': 'vnc_server', 'action': 'process', 'status': status, 'ip': self.ip, 'port': self.port, 'username': self.username, 'password': self.password}])

            if status == 'success':
                return True
            else:
                self.kill_server()
                return False
        else:
            self.vnc_server_main()

    def close_port(self):
        ret = close_port_wrapper('vnc_server', self.ip, self.port, self.logs)
        return ret

    def kill_server(self):
        ret = kill_server_wrapper('vnc_server', self.uuid, self.process)
        return ret


if __name__ == '__main__':
    parsed = server_arguments()
    if parsed.docker or parsed.aws or parsed.custom:
        qvncserver = QVNCServer(ip=parsed.ip, port=parsed.port, username=parsed.username, password=parsed.password, mocking=parsed.mocking, config=parsed.config)
        qvncserver.run_server()
