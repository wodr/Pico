**Measure duration between input pin changes with PIO**

Measure duration between input pin changes.
Exact frequency and duty cycle measurements for low range frequncies (< 3 kHz).

The basic idea is to count instruction between changes of the input pin. 
Because each instruction has a well defined duration the frequency can be calculated.

PIO program:

- wait in a loop for input high
- in the loop decrement a counter 
- each loop takes 5 cylces
- when the input is high publish the counter in the rx fifo
- do the same for input low.

The statemachine runs at 125Mhz. That means each cylce takes 8 ns.
The input change is detected with a granularity of 5 instructions * 8 ns / instruction = 40ns.
Given this the accuracy is better than 0.008%  for frequencies up  to 1000 Hz.
There are some more instructions between the counting loops, which also wiggle the result.
But these are a fixed time and only occour once for each signal change.

The frequency is limit to about 3 kHz, because of the slow interrupt handler to empty the rx fifo.
This might be improved , if the values are written in a dma buffer, so that interrupts rate could be lowered to read the buffer

Example output for a 50 Hz signal with 50% duty cylce:

Low [#]  : Counter for input low  
High[#]  : Counter for input high  
H+L [#]  : Sum of low and high counter

```
 Time   Loops      Low [#]   High [#]  H+L[#]  Period [ms]    Frequency [Hz]  Duty [%]
--------------------------------------------------------------------------------------
 505      24       249998    249998    499996     19.9998      50.0004         50     
 505      49       249998    249998    499996     19.9998      50.0004         50     
 506      74       249998    249999    499997     19.9999      50.0003         49.9999 
 505      100      249998    249999    499997     19.9999      50.0003         49.9999 
 505      125      249998    249998    499996     19.9998      50.0004         50     
 ```

 Example output for 1000 Hz signal with 25% duty: 
 ```
 Time   Loops      Low [#]   High [#]  H+L[#]  Period [ms]    Frequency [Hz]  Duty [%]
--------------------------------------------------------------------------------------
 540      488      6250      18750     25000      1            1000            25     
 501      1016     6250      18750     25000      1            1000            25     
 537      1524     6250      18750     25000      1            1000            25     
 501      2053     6250      18750     25000      1            1000            25     
 548      2572     6250      18750     25000      1            1000            25     
 547      3119     6250      18749     24999      0.99996      1000.04         25.001 
 501      3650     6250      18749     24999      0.99996      1000.04         25.001 
 547      4166     6250      18750     25000      1            1000            25     
 ```

   Example output for 93 Hz signal with 6.25 duty: 
 ```
 Time   Loops      Low [#]   High [#]  H+L[#]  period [ms]    frequency [Hz]  Duty [%]
--------------------------------------------------------------------------------------
 509      44       16799     252019    268818     10.7527      92.9997         6.24921 
 509      91       16800     252018    268818     10.7527      92.9997         6.24958 
 510      139      16799     252018    268817     10.7527      93.0001         6.24923 
 510      186      16800     252018    268818     10.7527      92.9997         6.24958 
 509      234      16799     252018    268817     10.7527      93.0001         6.24923 
 510      281      16800     252018    268818     10.7527      92.9997         6.24958 
 510      329      16799     252018    268817     10.7527      93.0001         6.24923 
 ```

Example output for 2000 Hz signal with 50 duty: 

```
 Time   Loops      Low [#]   High [#]  H+L[#]  Period [ms]    Frequency [Hz]  Duty [%]
--------------------------------------------------------------------------------------
 501      980      6250      6250      12500      0.5          2000            50     
 501      1968     6250      6250      12500      0.5          2000            50     
 501      2953     6250      6250      12500      0.5          2000            50     
 501      3942     6250      6250      12500      0.5          2000            50     
 501      4930     6250      6250      12500      0.5          2000            50     
 ```

