
# Example using PIO to wait for a pin change and raise an IRQ.
#
# Demonstrates:
#   - PIO wrapping
#   - PIO wait instruction, waiting on an input pin
#   - PIO irq instruction, in blocking mode with relative IRQ number
#   - setting the in_base pin for a StateMachine
#   - setting an irq handler for a StateMachine
#   - instantiating 2x StateMachine's with the same program and different pins

import time
from machine import Pin
import rp2


@rp2.asm_pio(autopush=True, fifo_join=rp2.PIO.JOIN_RX)
def wait_pin_high():
    wrap_target()

    set(x, 7) # read 8 words
    set(y, 31) # with 32 bits each

    wait(1, pin, 0)
    
    label("read")
    in_(pins, 1)
    jmp(y_dec, "read_delayed")
    set(y, 31) # with 32 bits each
    jmp(x_dec, "read") # continue reading next word

    jmp("irq")

    label("read_delayed")
    jmp("read")

    label("irq")
    irq(block, rel(0))



def handler(sm):
    # Print a (wrapping) timestamp, and the state machine object.
    n_words = sm.rx_fifo()
    res = ''
    for _ in range(n_words):
        res += f'{sm.get():032b}'
        
    print(time.ticks_ms(), res)


# Instantiate StateMachine(0) with wait_pin_low program on Pin(16).
input_pin= Pin(15, Pin.IN, Pin.PULL_UP)
sm0 = rp2.StateMachine(0, wait_pin_high, freq=12000, in_base=input_pin)
sm0.irq(handler)

# Start the StateMachine's running.
sm0.active(1)

# Now, when Pin(16) or Pin(17) is pulled low a message will be printed to the REPL.
