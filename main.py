from asyncio import get_event_loop, create_task, sleep_ms
from lora import LoRa
from button import Button

lora = LoRa(bandwidth=9, password='1234abcd', debug=1)
lora.create_tasks()

beep_button = Button(11, pull_down=False)
boop_button = Button(15, pull_down=False)


async def boop():
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


async def beep():
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


async def print_msg():
    await lora.initialized.wait()

    while True:
        await lora.message_flag.wait()
        if msg := lora.get_message():
            print(msg)
        else:
            await sleep_ms(250)
            print("No new messages")

create_task(boop())
create_task(beep())
create_task(print_msg())
get_event_loop().run_forever()
