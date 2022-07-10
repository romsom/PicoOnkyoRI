
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

@rp2.asm_pio(fifo_join=rp2.PIO.JOIN_TX, out_init=rp2.PIO.OUT_LOW)
def send_onkyo_ri():
    # this should run with 3kHz to get 1ms timings
    wrap_target()

    pull()
    # write out 4 header states and the up to 36 pin states for our
    # 12 bits + one high and at least one low
    set(x, 31)
    set(y, 28)
    label("write_bits_0")
    nop()
    out(pins, 1)
    jmp(x_dec, "write_bits_0")

    pull()
    # 4 + 4 + 2 would suffice, but there is a minimum delay
    # of 20ms after the falling edge of the footer,
    # we just keep writing
    label("write_bits_1")
    out(pins, 1)
    jmp(y_dec, "write_bits_1")[1]

    
    wrap()

@rp2.asm_pio(autopush=True, fifo_join=rp2.PIO.JOIN_RX)
def receive_onkyo_ri():
    wrap_target()

    set(x, 7) # read 8 header high bits

    wait(1, pin, 0)
    
    label("read_header")
    in_(pins, 1)
    jmp(x_dec, "read_header")
    nop()[1] # 9th bit
    # 3 header low bits
    nop()[1] # 1st bit
    in_(pins, 1)[1] # in_(pins, 1)
    nop() # 3rd bit

    set(x, 17) # 12 bits, one high phase, possibly 2 low -> 36 phases -> 36 bits
    label("read_bit")
    nop()[1] # 1st sample
    in_(pins, 1)[1]
    nop()[1] # 3rd sample
    # next phase
    nop()[1] # 1st sample
    in_(pins, 1)[1]
    nop() # 3rd sample
    jmp(x_dec, "read_bit")

    # we have 8 + 1 + 36 = 45 bits, so we need to pad them to 64 bits
    set(x, 18) # 12 bits, one high phase, possibly 2 low -> 36 phases -> 36 bits

    label("read_padding_bit")
    in_(pins, 1)
    jmp(x_dec, "read_padding_bit")

    # push()

    irq(block, rel(0))
    wrap()


def handler(sm):
    # Print a (wrapping) timestamp, and the state machine object.
    n_words = sm.rx_fifo()

    if n_words >= 2:
        word_0 = sm.get()
        if (word_0 >> 23) != 0x1fe:
            print('invalid header')
            return
        # res = 0
        # next_sample = 23
        # bits_remaining = 12

        # while next_sample >= 2:
        #     hi_state = (word_0 >> next_sample) & 0x1
        #     if hi_state != 1:
        #         print('invalid data')
        #         return

        #     bit_state = (word_0 >> (next_sample - 2)) & 0x1
        #     res <<= 1
        #     res += bit_state
        #     bits_remaining -= 1
        #     next_sample -= 3 - bit_state # advance 2 or 3 bits

        # if next_sample == 1:
        #     hi_state = (word_0 >> next_sample) & 0x1
        #     if hi_state != 1:
        #         print('invalid data')
        #         return

        #     bit_state = (word_0 >> (next_sample - 2)) & 0x1
        #     res <<= 1
        #     res += bit_state
        #     bits_remaining -= 1
        #     next_sample -= 2 + bit_state # advance 2 or 3 bits
        word_1 = sm.get()
        data = ((word_0 & 0x7fffff) << 32 + 9) + (word_1 << 9)
        n_remaining = n_words - 2
        while n_remaining > 0:
            print('found extra data: ', sm.get())
            n_remaining -= 1
    
        res = 0
        next_sample = 63
        bits_remaining = 12

        while bits_remaining > 0:
            hi_state = (data >> next_sample) & 0x1
            if hi_state != 1:
                print('invalid data')
                return

            bit_state = (data >> (next_sample - 2)) & 0x1
            res <<= 1
            res += (1-bit_state)  # somehow making this inverse makes it match the lirc docs for tape control
            bits_remaining -= 1
            next_sample -= 3 - bit_state # advance 2 or 3 bits
                
            
        
        print(time.ticks_ms(), f'0x{res:03x}')
        # print(f'{word_0:032b}')
        # print(f'{word_1:032b}')

def send_ri(command, sm):
    cmd = command & 0xfff
    states = 7 << (63 - 2)
    next_hi_state = 63 - 4

    for i in range(11, -1, -1):
        states += 1 << next_hi_state
        # command bit 1 -> += 2, 0 -> += 3
        # next_hi_state -= 3 - ((cmd >> i) & 0x1)
        next_hi_state -= 2 + ((cmd >> i) & 0x1) # invert to match receiver side

    # set footer
    states += 1 << next_hi_state
    # print(f'{states:064b}')
    word_0 = states >> 32
    word_1 = states & ((1<<32) - 1)
    # print(f'{word_0:032b}')
    # print(f'{word_1:032b}')

    sm.put(word_0)
    sm.put(word_1)

    # print(sm.tx_fifo())

def scan_ri(sm, start, end, increment):
    for cmd in range(start, end, increment):
        print(f'Scan 0x{cmd:x}')
        send_ri(cmd, sm)
        time.sleep(2)
        
# Instantiate StateMachine(0) with wait_pin_low program on Pin(16).
input_pin= Pin(15, Pin.IN, Pin.PULL_UP)
sm0 = rp2.StateMachine(0, receive_onkyo_ri, freq=6000, in_base=input_pin)
sm0.irq(handler)
output_pin= Pin(14, Pin.OUT, value=0)
sm1 = rp2.StateMachine(1, send_onkyo_ri, freq=3000, out_base=output_pin)

# Start the StateMachine's running.
sm0.active(1)
sm1.active(1)
