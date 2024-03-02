from machine import Pin, SPI, I2C, reset
from lora_display import LoRaDisplay
# from lora import LoRa
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


# lora = LoRa(address=3, reset_pin=2, bandwidth=9, password='1234abcd', debug=1)

transceiver_spi = SPI(0, miso=Pin(0), mosi=Pin(3), sck=Pin(2), baudrate=868500000)

adc_spi = SPI(0, sck=Pin(18), miso=Pin(16), mosi=Pin(19), baudrate=100000)
adc_cs = Pin(17, Pin.OUT)

loop = get_event_loop()

loop.set_exception_handler(exception_handler)
loop.run_forever()

