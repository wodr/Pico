import time
from machine import Pin,PWM,freq
from array import array
import rp2



# Configuration    GPIO  PIN  GPIO        Configuration
#------------------------------------------------------
#                     0    1    VUSB     
#                     1    2    VSYS 
#                   GND    3    GND 
#                     2    4    3V3_EN    
#                     3    5    3V3(out)    
#                     4    6    ADC_REF    
#                     5    7    28
#                   GND    8    GND 
#                     6    9    27
#                     7    10   26
#                     8    11   RUN
#                     9    12   22          in.pullup
#                   GND    13   GND
#                    10    14   21
#                    11    15   20  
#                    12    16   19  
#                    13    17   18  
#                   GND    18   GND
#                    14    19   17  
#      out           15    20   16          PWM 

#https://docs.micropython.org/en/latest/library/rp2.StateMachine.html#rp2.StateMachine
# inspired by : https://github.com/dhylands/upy-examples/blob/master/pico/pio_measure.py
@rp2.asm_pio(set_init=rp2.PIO.IN_LOW, autopush=True, push_thresh=32,sideset_init=rp2.PIO.OUT_HIGH)
def measureTime():
    wrap_target()
    set(x, 0)
    label('wait0')
    jmp(x_dec, 'next0') [1]     # delay for 1 instruction because next loop take 1 more instruction
    label('next0')              # delay can be set to 0 if instructionCounterHigh = 2
    jmp(pin, 'wait0')           # while pin is high
    in_(x, 32).side(0)          # push low duration 
    
    set(x, 0)
    label('wait1')              # pin pin is low
    jmp(x_dec, 'next1') 
    label('next1') 
    jmp(pin, 'done')            # pin has gone high: all done
    jmp('wait1')
    label('done')
    mov(x,invert(x))
    in_(x, 32).side(1)          # push high duration
    wrap()

rp2.PIO(0).remove_program() # reset all
rp2.PIO(0).irq(None)
for i in range(0,4):
    rp2.StateMachine(i).irq(None)

measurePin = None
usePwm = True
if( usePwm ):
    measurePin = Pin(13,Pin.IN,Pin.PULL_UP)
    pinPwm = PWM(measurePin)    
    pinPwm.freq(100)
    pinPwm.duty_u16(int(0x8000))    # 50%
    #pinPwm.duty_u16(int(0x4000))   # 25%
    #pinPwm.duty_u16(int(0x1000))   # 50%
else:
    measurePin = Pin(22,Pin.IN,Pin.PULL_UP)

sideSetPin = Pin(10,Pin.OUT)

sm0 = rp2.StateMachine(0, measureTime, in_base=measurePin,sideset_base=sideSetPin,jmp_pin=measurePin)
print(f"for signal on {measurePin} machine f= {freq()} Hz sideSet {sideSetPin}")


sm0.active(1)
loops = 0

def Read():
    read = 0
    def SingleRead(timeout=5.0):
        start = time.ticks_ms()                
        while(time.ticks_ms() - start < timeout*1000):
            if( sm0.rx_fifo() > 0 ):
                yield sm0.get()       
                start = time.ticks_ms()  
            else:
                time.sleep(0.001)        
    
    it = iter(SingleRead())
    
    while(True):
        # always wait for 2 values to calculate duty cycle                
        highCount=0
        lowCount=0
        try:
            while( True ):
                highCount = next(it)
                if( highCount & 0x80_00_00_00):
                    break
            highCount = 0xFF_FF_FF_FF - highCount
            lowCount = next(it)        
        except StopIteration:
            print("no values")
            return
        read +=1
        #print(f"{highCount:08x} {lowCount:08x}")
        yield (read,lowCount*3*8e-9,highCount*3*8e-9)        
        

start = time.ticks_ms()
print(" Time   Loops      Low [ms]   High [ms]   Period [ms]    Frequency [Hz]       Duty [%]   error [%]")
print("----------------------------------------------------------------------------------------------------")
#       505      51       4.99999   4.99985   9.99984      100.002         50.0007     0.0016
instructionCounterLow = const(3)
instructionCounterHigh = const(3)
for (read,lowCount,highCount) in Read():        
    
       
    denominator = (lowCount + highCount)
    if( denominator == 0):
        print(f"{read} {lowCount} {highCount} {denominator}")
        continue
        
    duty = highCount / denominator
    
    # 
    # each instruction is 8 ns at 125 MHz frequency
    # 3 instructions are used for one loop
    # period  = denominator * (8e-9 * 3)    
    # for if 2 - 3 instructions are use:
    period = lowCount + highCount
    if( period != 0):
        fr = 1/period
    else:
        fr = -1
    expectedFr = round(fr,0)
    abserror = abs(expectedFr- fr)
    if( expectedFr == 0 ):
        expectedFr = 1

    error = abserror / expectedFr
    
    error *= 100 
    loops += 1
    # print only each 0.5 seconds
    if( time.ticks_ms() - start >  50):
        print(f" {time.ticks_ms()-start:<8} {loops:<8} {highCount*1e3:<12} {lowCount*1e3:<12} {period*1000:<12}     {fr:<9}       {duty*100:<7}     {error:3.3}") 
        start = time.ticks_ms()
    
sm0.active(0)
print("done")





