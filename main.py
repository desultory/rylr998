from asyncio import get_event_loop, create_task, sleep_ms
from lora import LoRa
from lora_net import LoRaNet
from button import Button
from machine import Pin, reset
from time import sleep_ms as _sleep_ms
from neopixel import NeoPixel


def exception_handler(loop, e):
    print(f"[{loop}: {e}")
    for _ in range(100):
        Pin("LED").toggle()
        _sleep_ms(50)
    raise e
    reset()


beep_button = Button(11, pull_down=False)
boop_button = Button(15, pull_down=False)


async def boop(boop_button, lora):
    await lora.initialized.wait()
    while True:
        print("Waiting to boop")
        if boop_button.value:
            print("boop")
            await lora.send_message('boop', 0)
            print("booped")
        else:
            print("sleeping booper")
            await sleep_ms(250)


async def beep(beep_button, lora):
    await lora.initialized.wait()
    while True:
        print("Waiting to BEEP")
        if beep_button.value:
            print("BEEP")
            await lora.send_message('BEEP', 0)
            print("BEEPed")
        else:
            print("sleeping BEEPer")
            await sleep_ms(250)


async def light(np, lora_net):
    while True:
        if lora_net.friends:
            print(lora_net.friends)
            signal = sum(int(data[1]) for data in lora_net.friends.values()) / len(lora_net.friends)
            np[0] = (64, 0, int(min(32 * signal, 255)))
        else:
            np[0] = (80, 110, 0)
        print(np[0])
        np.write()
        await sleep_ms(300)


def print_msg(msg):
    print(msg)


np = NeoPixel(Pin(6), 1)
np[0] = (0, 255, 0)
np.write()


lora = LoRa(bandwidth=9, password='1234abcd', debug=1)
lora_net = LoRaNet(lora, message_callback=print_msg, beacon_interval=5, client_timeout=5)
lora_net.start()

# create_task(boop())
# create_task(beep())
create_task(light(np, lora_net))
loop = get_event_loop()

loop.set_exception_handler(exception_handler)
loop.run_forever()
reset()
