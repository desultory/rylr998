from asyncio import sleep, create_task, TimeoutError, wait_for
from time import ticks_ms, ticks_diff
from lora import LoRa


class LoRaNet:
    def __init__(self, lora, beacon_interval=60, client_timeout=300, beacon_message='HELLO',
                 beacon_callback=None, message_callback=None, key='zen'):
        if not isinstance(lora, LoRa):
            raise ValueError("A LoRa object must be passed.")
        self.lora = lora
        self.beacon_interval = beacon_interval
        self.beacon_message = beacon_message
        self.client_timeout = client_timeout
        self.key = key

        self.beacon_task = None
        self.beacon_callback = beacon_callback
        self.message_callback = message_callback
        self.friends = {}

    @property
    def beacon_response(self):
        from hashlib import sha256
        from binascii import b2a_base64
        response = sha256()
        response.update(self.beacon_message + self.key)
        return b2a_base64(response.digest()).decode().rstrip()

    def start(self):
        if not self.lora.initialized.is_set():
            self.lora.create_tasks()
        else:
            print("LoRa object is already initialized")
        create_task(self.runloop())

    async def runloop(self):
        await self.lora.initialized.wait()
        print("Starting LoRaNet runloop")
        if not self.beacon_task or self.beacon_task.cancelled():
            self.beacon_task = create_task(self.beacon())
        while True:
            try:
                await wait_for(self.lora.message_flag.wait(), self.client_timeout)
            except TimeoutError:
                pass

            if msg := self.lora.get_message():
                if self.message_callback:
                    self.message_callback(msg)
                if msg.data == self.beacon_message:
                    await self.lora.send_message(self.beacon_response, msg.sender)
                elif msg.data == self.beacon_response:
                    self.friends[msg.sender] = (msg.rssi, msg.snr, ticks_ms())

            expired_peers = []
            for friend, info in self.friends.items():
                rssi, snr, time = info
                if ticks_diff(ticks_ms(), time) > self.client_timeout * 1000:
                    expired_peers += friend

            for peer in expired_peers:
                print("Removing stale peer: ", peer)
                self.friends.pop(peer)

            print(self.friends)

    async def beacon(self):
        await self.lora.initialized.wait()
        print(f"[{self.lora.address}@{self.lora.network}] Beaconing '{self.beacon_message}' every {self.beacon_interval} seconds.")
        while True:
            if self.beacon_callback:
                self.beacon_callback(f"[b] {self.beacon_message}")
            try:
                await self.lora.send_message(self.beacon_message)
            except TimeoutError:
                print("Module timed out sending beacon, resetting.")
                await self.lora.reset()
            await sleep(self.beacon_interval)





