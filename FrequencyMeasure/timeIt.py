import time
from machine import Pin,PWM,freq
from array import array
import rp2

# irq(1) => flags == 512
# irq(0) => flags == 256

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

@rp2.asm_pio(sideset_init=rp2.PIO.OUT_HIGH,push_thresh=1)
def measureTime():
    wrap_target()        
    set(y,0) 
    label('wait0')
    jmp(y_dec,'next0')      # y = 0xFFFFFFFF contains loop couter     
    label('next0')          # each loop takes a 5 cylces
    in_(pins,1)             # so the time is the cycle time times y 
    mov(x,isr)  
    mov(x,x)                # nop to have 5 instructions per loop
                      
    jmp(not_x,'wait0')      # jump to wait if pin == 1
    
    nop().side(0)           # now pin is 0    
    in_(y,32)
    push()      
    irq(0)                  # publish duration y

    set(y,0) 
    label('wait1')  
    jmp(y_dec,'next1')      # init y with 0xFFFFFFFF 
    label('next1')                              
    mov(isr,0)              # clear isr, so that the next read has value 1 or 0 and does not shift a previous!
    in_(pins,1)    
    mov(x,isr)
    jmp(x_dec,'wait1')      # wait until pin is 0  
    nop().side(1)           # now pin is 1
  
    in_(y,32)               # publish y 
    push()  
    irq(1)

    wrap()

rp2.PIO(0).remove_program() # reset all
rp2.PIO(0).irq(None)
rp2.PIO(1).irq(None)
for i in range(0,8):
    rp2.StateMachine(i).irq(None)

pin = None
usePwm = True
if( usePwm ):
    pin = Pin(13,Pin.IN,Pin.PULL_UP)
    pinPwm = PWM(pin)    
    pinPwm.freq(3000)
    pinPwm.duty_u16(int(0x8000)) # 50%
    #pinPwm.duty_u16(int(0x4000))  # 25%
    #pinPwm.duty_u16(int(0x1000)) # 50%
else:
    pin = Pin(22,Pin.IN,Pin.PULL_UP)

sideSetPin = Pin(15,Pin.OUT)

sm0 = rp2.StateMachine(0, measureTime, in_base=pin,sideset_base=sideSetPin)
print(f"for signal on {pin} machine f= {freq()} Hz sideSet {sideSetPin}")


write = 0 
records  = array('L',[0]*1024)

def interrupHandler(sm):
    global write
    flag = sm.irq().flags()
    try:
        count = sm0.rx_fifo()
        if( count == 0 ):
            #print("ERROR FIFO EMPTY")
            return
    except NameError:
        # todo fix: NameError: name 'sm0' isn't defined
        return
    
    val = 0xffff_ffff -  sm0.get()      # causes MemoryError if execute in hard mode.
    # write to ringbuffer             
    if( flag & 0x100):   
        records[write] = val
    else:        
        records[write+1] = val
        write = (write+2) & 0x3FF     # only increment write after both value are written   

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
    
    it = iter(SingleRead())
    
    while(True):
        # always wait for 2 values to calculate duty cycle
        read,lowCount = next(it)
        read,highCount = next(it)        
        yield (read-2,lowCount,highCount)        
        

start = time.ticks_ms()
print(" Time   Loops      Low [#]   High [#]  H+L[#]  Period [ms]    Frequency [Hz]  Duty [%]")
print("--------------------------------------------------------------------------------------")

for (read,lowCount,highCount) in Read():        
    lowCount += 2 # add a little for the overhead of non loop instructions
    highCount += 2
    denominator = lowCount+highCount
    if( denominator == 0):
        print(f"{write} {read} {lowCount} {highCount} {denominator}")
        continue
        
    duty = highCount / denominator
    
    # 
    # each instruction is 8 ns at 125 MHz frequency
    # 5 instructions are used for one loop
    period  = denominator * (8e-9 * 5)
    if( period != 0):
        fr = 1/period
    else:
        fr = -1
    loops += 1
    # print only each 0.5 seconds
    if( time.ticks_ms() - start >  500):
        print(f" {time.ticks_ms()-start:<8} {loops:<8} {highCount:<9} {lowCount:<9} {denominator:<8}   {period*1000:<8}     {fr:<9}       {duty*100:<6} ") 
        start = time.ticks_ms()

sm0.active(0)
sm0.irq(None)
rp2.PIO(0).irq(None)
print("done")
