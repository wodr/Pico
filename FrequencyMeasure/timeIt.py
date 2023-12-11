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
# https://docs.micropython.org/en/latest/library/rp2.StateMachine.html#rp2.StateMachine
@rp2.asm_pio(set_init=rp2.PIO.IN_LOW, autopush=True, push_thresh=32)
def measureTime():
    wrap_target()
    set(x, 0)
    label('wait0')
    jmp(x_dec, 'next0') [1]     # delay for 1 instruction because next loop take 1 more instruction
    label('next0')              # delay can be set to 0 if instructionCounterHigh = 2
    jmp(pin, 'wait0')           # while pin is high
    in_(x, 32)                  # push low duration 
    
    set(x, 0)
    label('wait1')              # pin pin is low
    jmp(x_dec, 'next1') 
    label('next1') 
    jmp(pin, 'done')            # pin has gone high: all done
    jmp('wait1')
    label('done')
    in_(x, 32)                  # push high duration
    # irq(1) => flags == 512
    # irq(0) => flags == 256
    irq(0)                      # only one interrupt for 2 fifo fills
    wrap()

rp2.PIO(0).remove_program() # reset all
rp2.PIO(0).irq(None)
rp2.PIO(1).irq(None)
for i in range(0,8):
    rp2.StateMachine(i).irq(None)

measurePin = None
usePwm = False
if( usePwm ):
    measurePin = Pin(13,Pin.IN,Pin.PULL_UP)
    pinPwm = PWM(measurePin)    
    pinPwm.freq(10)
    #pinPwm.duty_u16(int(0x8000))    # 50%
    pinPwm.duty_u16(int(0x4000))   # 25%
    #pinPwm.duty_u16(int(0x1000))   # 50%
else:
    measurePin = Pin(21,Pin.IN)

sideSetPin = Pin(15,Pin.OUT)

sm0 = rp2.StateMachine(0, measureTime, in_base=measurePin,sideset_base=sideSetPin,jmp_pin=measurePin)
print(f"for signal on {measurePin} machine f= {freq()} Hz sideSet {sideSetPin}")


write = 0 
records  = array('L',[0]*1024)
exitRequest = False
def interrupHandler(sm):
    try:
        global write,exitRequest
        flag = sm.irq().flags()
        try:
            count = sm0.rx_fifo()
            if( count == 0 ):
                #print("ERROR FIFO EMPTY")
                return
        except NameError:
            # todo fix: NameError: name 'sm0' isn't defined
            return
        tmp = write
        while(sm0.rx_fifo() > 0 ):
            val = 0xffff_ffff -  sm0.get()      # causes MemoryError if execute in hard mode.
            records[tmp] = val
            tmp = (tmp + 1)  & 0x3FF   
        # expect always multiple of 2
        write = tmp   # set after all values are written
    except KeyboardInterrupt:
        print("exit")
        exitRequest= True
    
    return   

rp2.PIO(0).irq(interrupHandler,hard=False)
sm0.active(1)
loops = 0

def Read():
    read = 0
    infoCounter = 0
    def SingleRead():
        while(True):
            nonlocal read, infoCounter
            while(read != write):
                val = records[read]
                read+=1
                yield (read,val)                
                read &= 0x3FF
                infoCounter=0
            infoCounter += 1
            if( infoCounter > 100):
                print(f"no data write = {write} read = {read}")
                infoCounter = 0
            time.sleep(0.01)
            if( exitRequest ):
                break
    
    it = iter(SingleRead())
    
    while(True):
        # always wait for 2 values to calculate duty cycle                
        try:
            read,highCount = next(it)
            read,lowCount = next(it)        
        except StopIteration:
            return

        yield (read-2,lowCount,highCount)        
        

start = time.ticks_ms()
print(" Time   Loops      Low [#]   High [#]  Instr[#]  Period [ms]    Frequency [Hz]  Duty [%]   error [%]")
print("----------------------------------------------------------------------------------------------------")

instructionCounterLow = const(3)
instructionCounterHigh = const(3)
for (read,lowCount,highCount) in Read():        
    
   
    lowCount += 2 # add a little for the overhead of non loop instructions
    highCount += 1
    
    denominator = (lowCount * instructionCounterLow + highCount *instructionCounterHigh)
    if( denominator == 0):
        print(f"{write} {read} {lowCount} {highCount} {denominator}")
        continue
        
    duty = highCount * instructionCounterHigh/ denominator
    
    # 
    # each instruction is 8 ns at 125 MHz frequency
    # 3 instructions are used for one loop
    # period  = denominator * (8e-9 * 3)    
    # for if 2 - 3 instructions are use:
    period = lowCount * (8e-9 *instructionCounterLow) + highCount*(8e-9*instructionCounterHigh)
    if( period != 0):
        fr = 1/period
    else:
        fr = -1
    expectedFr = round(fr,0)
    abserror = abs(expectedFr- fr)
    error = abserror / expectedFr
    error *= 100 
    loops += 1
    # print only each 0.5 seconds
    if( time.ticks_ms() - start >  500):
        print(f" {time.ticks_ms()-start:<8} {loops:<8} {highCount:<9} {lowCount:<9} {denominator:<8}   {period*1000:<8}     {fr:<9}       {duty*100:<7}     {error:3.3}") 
        start = time.ticks_ms()
    
sm0.active(0)
sm0.irq(None)
rp2.PIO(0).irq(None)
print("done")





