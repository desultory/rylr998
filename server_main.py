from machine import Pin, SPI, I2C, reset
from mcp3008 import MCP3008
from lora_display import LoRaDisplay
from lora import LoRa
from lora_net import LoRaNet
from time import sleep_ms as _sleep_ms
from asyncio import get_event_loop, create_task


def exception_handler(loop, e):
    print(f"[{loop}: {e}")
    for _ in range(100):
        Pin("LED").toggle()
        _sleep_ms(50)
    raise e['exception']
    reset()


display_i2c = I2C(1, scl=Pin(15), sda=Pin(14))
lora = LoRa(address=3, reset_pin=2, bandwidth=9, password='1234abcd', debug=1)

try:
    display = LoRaDisplay(lora, display_i2c)
except Exception as e:
    print(e)
    _sleep_ms(5000)
    reset()

lora_net = LoRaNet(lora, beacon_callback=display.beacon_callback, message_callback=display.message_callback)

adc_spi = SPI(0, sck=Pin(18), miso=Pin(16), mosi=Pin(19), baudrate=100000)
adc_cs = Pin(17, Pin.OUT)

adc = MCP3008(adc_spi, adc_cs)


create_task(display.runloop())
lora_net.start()

loop = get_event_loop()

loop.set_exception_handler(exception_handler)
loop.run_forever()

