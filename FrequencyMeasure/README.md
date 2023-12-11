**Measure duration between input pin changes with PIO**

Measure duration between input pin changes.
Exact frequency and duty cycle measurements for low range frequncies (< 5 kHz).

The basic idea is to count instruction between changes of the input pin. 
Because each instruction has a well defined duration the frequency can be calculated.

PIO program:

- wait in a loop for input high
- in the loop decrement a counter 
- each loop takes 3 cylces
- when the input is high publish the counter in the rx fifo
- do the same for input low.
- fire an interrupt

The statemachine runs at 125Mhz. That means each cylce takes 8 ns.
The input change is detected with a granularity of 3 instructions * 8 ns / instruction = 24ns.
Given this the accuracy is better than 0.003%  for frequencies up  to 1000 Hz.
There are some more instructions between the counting loops, which also wiggle the result.
But these are a fixed time and only occour once for each signal change.

The frequency is limit to about 3 kHz, because of the slow interrupt handler to empty the rx fifo.
This might be improved , if the values are written in a dma buffer, so that interrupts rate could be lowered to read the buffer

Example output for a 50 Hz signal with 50% duty cylce:

Low [#]  : Counter for input low  
High[#]  : Counter for input high  
H+L [#]  : Sum of low and high counter

Example output for 50 Hz signal with 50% duty: 

```
 Time   Loops      Low [#]   High [#]  H+L[#]  Period [ms]    Frequency [Hz]  Duty [%]
--------------------------------------------------------------------------------------
 507      26       416664    416664    833328     19.9999      50.0003         50     
 506      51       416663    416664    833327     19.9998      50.0004         49.9999 
 517      77       416664    416664    833328     19.9999      50.0003         50     
 517      103      416663    416664    833327     19.9998      50.0004         49.9999 
 517      129      416664    416663    833327     19.9998      50.0004         50.0001 
 ```

 Example output for 1000 Hz signal with 25% duty: 
 ```
 Time   Loops      Low [#]   High [#]  H+L[#]  Period [ms]    Frequency [Hz]  Duty [%]
--------------------------------------------------------------------------------------
 511      496      31249     10417     41666      0.999984     1000.02         25.0012 
 509      1002     31249     10417     41666      0.999984     1000.02         25.0012 
 501      1500     31249     10417     41666      0.999984     1000.02         25.0012 
 510      2006     31249     10417     41666      0.999984     1000.02         25.0012 
 511      2513     31249     10417     41666      0.999984     1000.02         25.0012 
 506      3021     31250     10416     41666      0.999984     1000.02         24.9988 
 ```

   Example output for 93 Hz signal with 6.25 duty: 
 ```
 Time   Loops      Low [#]   High [#]  H+L[#]  Period [ms]    Frequency [Hz]  Duty [%]
--------------------------------------------------------------------------------------
 502      46       420030    27999     448029     10.7527      92.9999         6.24937 
 502      93       420030    28000     448030     10.7527      92.9997         6.24958 
 501      140      420029    28000     448029     10.7527      92.9999         6.2496 
 501      187      420029    28000     448029     10.7527      92.9999         6.2496 
 502      233      420030    27999     448029     10.7527      92.9999         6.24937 
 ```

Example output for 2000 Hz signal with 50 duty: 

```
 Time   Loops      Low [#]   High [#]  H+L[#]  Period [ms]    Frequency [Hz]  Duty [%]
--------------------------------------------------------------------------------------
 511      978      10416     10417     20833      0.499992     2000.03         50.0024 
 501      1963     10416     10417     20833      0.499992     2000.03         50.0024 
 509      2966     10416     10417     20833      0.499992     2000.03         50.0024 
 501      3951     10416     10417     20833      0.499992     2000.03         50.0024 
 501      4941     10416     10417     20833      0.499992     2000.03         50.0024 
 502      5920     10417     10416     20833      0.499992     2000.03         49.9976 
 506      6918     10416     10417     20833      0.499992     2000.03         50.0024 
 ```

