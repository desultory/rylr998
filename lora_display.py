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
        if not self.lora.initialized:
            self.lora.create_tasks()
            await self.lora.initialized.wait()
        self.text_lines += 'LoRa initialized'

    def beacon_callback(self, msg):
        self.text_lines += msg + '\n'

    def message_callback(self, msg):
        self.text_lines += f'[{msg.sender}] {msg.data}\n'
        print(msg)

