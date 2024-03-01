from machine import Pin, SPI, I2C, reset
from mcp3008 import MCP3008
from lora_display import LoRaDisplay
from lora import LoRa
from time import sleep_ms as _sleep_ms
from asyncio import get_event_loop, create_task

display_i2c = I2C(1, scl=Pin(15), sda=Pin(14))
lora = LoRa(address=3, reset_pin=2, bandwidth=9, password='1234abcd')

try:
    display = LoRaDisplay(lora, display_i2c)
except Exception as e:
    print(e)
    _sleep_ms(5000)
    reset()

adc_spi = SPI(0, sck=Pin(18), miso=Pin(16), mosi=Pin(19), baudrate=100000)
adc_cs = Pin(17, Pin.OUT)

adc = MCP3008(adc_spi, adc_cs)


create_task(display.runloop())

get_event_loop().run_forever()

