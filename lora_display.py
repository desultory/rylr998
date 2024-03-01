from asyncio import sleep_ms, create_task
from display import Display
from lora import LoRa


class LoRaDisplay(Display):
    def __init__(self, lora, *args, **kwargs):
        if not isinstance(lora, LoRa):
            raise ValueError("lora must be a LoRa object.")
        self.lora = lora
        super().__init__(*args, **kwargs)

    async def start(self):
        await super().start()
        self.lora.start()
        await self.lora.initialized.wait()
        self.text_lines += 'LoRa initialized'
        create_task(self.get_msg())
        create_task(self.lora.beacon('hello', 5000, self.beacon_callback))

    def beacon_callback(self, msg):
        self.text_lines += msg + '\n'

    async def get_msg(self):
        while True:
            await self.lora.message_flag.wait()
            if msg := self.lora.get_message():
                self.text_lines += f'[{msg.sender}] {msg.data}\n'
                print(msg)
            else:
                await sleep_ms(250)
                print("No new messages")

