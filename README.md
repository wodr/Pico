**Demo RP2040 raspberry pico using PIO in micropython**

The HoldButton implements a button, that fires an interrupt, if the button is pushed, hold or released.
The scenario for using this kind of button is:
- Press once : switch LED on 
- Press again: switch LED off
- Hold  : control a PWM duty cycle up and down to dim a LED

```
Interrupts:

Sequence for short push:

   pressed released
----|---------|----> t

Sequence for long push:

   pressed       hold   hold   hold released
----|-------------|------|------|----|----> t
    
```

I did no observe any glitches and did not use any capacitor.

The button is configured as in, pull up.

The PIO (programmable input output) for the rp2040 is used to detected the button input changes:

- The PIO program waits for an input to get low and fires an interrupt.
- Then waits for the input to get high again in a loop.
- If the loop exits before the input is high a "hold" interrupt is fired.
- Then the loop is repeated
- If the button is finally released an interrupt is fired
- The program is started again

The loop time for a hold detection is configured by the frequency of the pio program 
and by the delay, set for the instructions.

The input fifo is used to add the kind of event: 
- pressed
- hold
- released

There are 8 buttons max, becaus there are 8 state machines.

I use the vscode extension MicroPico (https://marketplace.visualstudio.com/items?itemName=paulober.pico-w-go).

Example output:

```
active sm=2 StateMachine(2)
time     #   event  
0        47  pressed    1
162      48  released   4
1        49  pressed    1
563      50  hold       2
584      51  hold       2
604      52  hold       2
609      53  released   4
```