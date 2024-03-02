from machine import UART, Pin
from asyncio import StreamReader, StreamWriter, Event, Lock, sleep_ms, wait_for, TimeoutError
from time import ticks_ms, ticks_diff

LoRa_bands = {'EU': 868.1, 'US': 915.0}


class LoRaMessage:
    @staticmethod
    def from_str(packet):
        fields = packet.split(',')
        return LoRaMessage(fields[0], fields[1], fields[2], fields[3], fields[4])

    def __init__(self, sender, length, data, rssi, snr):
        self.sender = sender
        self.length = length
        self.data = data
        self.rssi = rssi
        self.snr = snr

    def __str__(self):
        return f"[{self.sender} <rssi: {self.rssi} snr:{self.snr}>] {self.data}"


class LoRa:
    AT_ALIASES = {'baud': 'ipr', 'parameters': 'parameter', 'network': 'networkid', 'password': 'cpin',
                  'power': 'crfop', 'version': 'ver'}

    RYLR_COMMANDS = {'reset': {'query': False, 'outputs': 2},
                     'mode': {'o1': [0, 1, 2]},
                     'ipr': {'o1': [300, 1200, 4800, 9600, 19200, 28800, 38400, 57600, 115200],
                             'o2': [None, 'm']},
                     'band': {'o1': [val * 1_000_000 for val in LoRa_bands.values()]},
                     'parameter': {'o1': (5, 11),
                                   'o2': (7, 9),
                                   'o3': (1, 4),
                                   'o4': (12)},
                     'address': {'o1': (0, 65535)},
                     'networkid': {'o1': [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 18]},
                     'cpin': {'o1': {'maxlen': 8, 'type': 'hexstr'}},
                     'crfop': {'o1': (0, 22)},
                     'send': {'o1': (0, 65535),
                              'o2': (0, 240),
                              'o3': {'maxlen': 240, 'type': 'ascii'}},
                     'uid': {'query': True},
                     'ver': {'query': True}}

    def __init__(self, uart=0, tx_pin=0, rx_pin=1, reset_pin=4, baudrate=115200,
                 band='US', address=2, network=18, password=None, power=22,
                 spreading_factor=11, bandwidth=9, coding_rate=1, preamble_length=12, debug=False):
        self.debug = debug
        self.uart = UART(uart, baudrate=baudrate, tx=tx_pin, rx=rx_pin)
        self.reset_pin = Pin(reset_pin, Pin.OUT)
        self.reader = StreamReader(self.uart)
        self.writer = StreamWriter(self.uart, {})

        self.band = band
        self.address = address
        self.network = network
        self.password = password
        self.power = power

        self.spreading_factor = spreading_factor
        self.bandwidth = bandwidth
        self.coding_rate = coding_rate
        self.preamble_length = preamble_length

        self.initialized = Event()
        self.seat = Lock()

        self.messages = []
        self.message_flag = Event()
        self.response_times = []
        self.response = None
        self.error = None

    def create_tasks(self):
        from asyncio import create_task
        create_task(self.readloop())
        create_task(self.dev_init())

    async def dev_init(self):
        await self.reset()
        for param in ['address', 'network', 'password', 'band']:
            await self.set_param(param)
        await self.set_param('parameters', self.spreading_factor, self.bandwidth, self.coding_rate, self.preamble_length)
        print(f"LoRa module initialized:\n{await self.to_str()}")
        self.initialized.set()

    async def send_message(self, message, target=0):
        print(f"[{target}@{self.network}] Sending message: {message}")
        target = int(target) if not isinstance(target, int) else target
        return await self.send_command('send', params=(target, len(message), message))

    def get_message(self):
        if not self.messages:
            self.message_flag.clear()
            return None
        else:
            if len(self.messages) == 1:
                self.message_flag.clear()
            return self.messages.pop()

    async def query(self, query):
        return await self.send_command(query, True)

    async def send_command(self, cmd, query=False, params=()):
        """ Sends an AT command to the device """
        cmd = self.AT_ALIASES[cmd] if cmd in self.AT_ALIASES else cmd
        if cmd not in self.RYLR_COMMANDS:
            raise ValueError("Invalid command: %s", cmd)

        if not query and not params:
            raise ValueError("Command missing parameters: %s", cmd)

        orig_cmd = cmd.upper()
        cmd = f"AT+{orig_cmd}"

        if query:
            cmd += "?\r\n"
        else:
            # Validate command data
            if not isinstance(params, tuple):
                params = (params,)
            cmd += '='
            for i, param in enumerate(params):
                option = self.RYLR_COMMANDS[orig_cmd.lower()][f'o{i + 1}']
                if isinstance(option, tuple):
                    if param < option[0] or param > option[1]:
                        raise ValueError(f"[{orig_cmd}] Value out of range: {param}")
                elif isinstance(option, list):
                    if param not in option:
                        raise ValueError(f"[{orig_cmd}] Value '{param} not in in: {option}")
                elif isinstance(option, dict):
                    if maxlen := option.get('maxlen'):
                        if len(param) > maxlen:
                            raise ValueError(f"[{orig_cmd}] Value '{param}' exceeds max length: {maxlen}")
                    if str_type := option.get('type'):
                        if str_type == 'hexstr':
                            try:
                                int(param, 16)
                            except ValueError:
                                raise ValueError(f"[{orig_cmd}] Value is not a hex string: {param}")
                        if str_type == 'ascii':
                            try:
                                param.encode('ascii')
                            except ValueError:
                                raise ValueError(f"[{orig_cmd}] Value is not an ascii string: {param}")

                cmd += f"{param},"
            cmd = f"{cmd[:-1]}\r\n"

        response = await self.send(cmd)
        if self.debug:
            print(f"Validating: {response}")
        # Do basic validation on the response, queries should return query data, commands should generally return OK
        if query:
            if response.startswith(f"{orig_cmd}="):
                response = response[len(f"{orig_cmd}="):]
            else:
                raise ValueError("Invalid response: %s" % response)
        elif response != 'OK':
            raise ValueError("[%s]Error: %s" % (cmd[:-2], response))
        return response

    async def send(self, data, timeout=5000):
        """ Sends a command over UART """
        start_time = ticks_ms()
        async with self.seat:
            if self.debug:
                print(f"Sending command: {data[:-2]}")
            await self.writer.awrite(data)
            await self.writer.drain()
            while not self.response:
                if ticks_diff(ticks_ms(), start_time) > timeout:
                    print("Response timed out")
                    raise TimeoutError("Got no response from LoRa module after timeout: %sms" % timeout)
                if self.debug:
                    print(f"Waiting for response, elapsed: {ticks_diff(ticks_ms(), start_time)}ms")
                await sleep_ms(10)
            if self.debug:
                print(f"Got response: {self.response}")
            response = self.response
            self.response = None
        return response

    async def readloop(self):
        print("Starting read loop.")
        while True:
            try:
                data = await self.recv()
                if self.debug:
                    print(f"Got data: {data.rstrip()}")
                    print(f"Average response time: {sum(self.response_times) / len(self.response_times)}")
            except TimeoutError:
                if self.debug:
                    print("No data received before timeout.")
            except ValueError as e:
                print(e)
                await self.reset()

    async def recv(self):
        """ Gets a single line from the UART, puts it in self.messages or self.response based on the data. """
        if self.debug:
            print("Waiting for data...")

        start_time = ticks_ms()
        data = await wait_for(self.reader.readline(), 15)
        self.response_times.append(ticks_diff(ticks_ms(), start_time))

        if data[-2:] != b'\r\n':
            raise ValueError("Data missing expected termination characters: %s", data)
        if data[0] != ord(b'+'):
            raise ValueError("Data missing expected start character '+': %s", data)

        data = data.decode()
        if data[:4] == '+RCV':
            if self.debug:
                print(f"Got new message: {data[:4]}")
            self.messages.append(LoRaMessage.from_str(data[5:-2]))
            self.message_flag.set()
        elif data[:4] == '+ERR':
            if self.debug:
                print(f"Error: {data[5:-2]}")
            self.error = (ticks_ms(), data[5:-2])
        else:
            self.response = data[1:-2]
        return data

    async def set_param(self, parameter, *args):
        """ Sets a modem config parameter. """
        if not args:
            args = getattr(self, parameter)
        if not args:
            print(f"Skipping empty parameter: {parameter}")
            return

        if func := getattr(self, f'set_{parameter}', None):
            response = await func(*args) if isinstance(args, tuple) else await func(args)
        else:
            response = await self.send_command(parameter, params=args)

        if isinstance(args, tuple) and len(args) == 1:
            setattr(self, parameter, args[0])
        else:
            setattr(self, parameter, args)
        return response

    async def set_band(self, band):
        """ Sets the band, the band can be a region code, float (freq/1000000) or plain int. """
        if isinstance(band, str):
            band = LoRa_bands[band]
        if isinstance(band, float):
            band = int(band * 1_000_000)

        response = await self.send_command('band', params=band)
        return response

    async def set_parameters(self, spreading_factor, bandwidth, coding_rate, preamble_length):
        if spreading_factor - 2 > bandwidth:
            raise ValueError("Invalid spreading factor '%s' for bandwidth: %s" % (spreading_factor, bandwidth))

        return await self.send_command('parameters', params=(spreading_factor, bandwidth, coding_rate, preamble_length))

    async def reset(self):
        print("Resetting LoRa module.")
        self.reset_pin.off()
        self.initialized.clear()
        await sleep_ms(100)
        self.reset_pin.on()
        await sleep_ms(50)
        if not self.response:
            raise RuntimeError("Module not responding after reset.")
        status = self.response
        self.response = None
        if status != 'READY':
            raise RuntimeError("Module not ready after reset: %s" % status)
        status = await self.send('AT\r\n')
        if status != 'OK':
            raise RuntimeError("Module is not responding to AT commands: %s" % status)
        if not await self.query('version') or not await self.query('uid'):
            raise RuntimeError("Unknown module.")

    async def to_str(self):
        out_str = ''
        for param, values in self.RYLR_COMMANDS.items():
            if values.get('query', True):
                val = await self.query(param)
                for p, v in self.AT_ALIASES.items():
                    if param == v:
                        param = p
                out_str += f"{param}: {val}\n"
        return out_str
