import time
from machine import Pin
from array import array
import rp2
from uctypes import addressof

PIO0_BASE = const(0x50200000)
PIO_RXF0 = const(0x20)


rp2.PIO(0).remove_program() # reset all
rp2.PIO(0).irq(None)
for i in range(0,4):
    try:
        rp2.StateMachine(i).irq(None)
        rp2.StateMachine(i).active(0)
    except:
        pass

@rp2.asm_pio(autopush=True,autopull=False, push_thresh=32)
def PioCounter():    
    pull(noblock)
    wrap_target()
    mov(y, osr)                 # y is delay    
    label("loop")               # delay 
    jmp(y_dec, "loop")    
    jmp(x_dec,"done")           # current counter value, each loop one less
    label("done")
    in_(x,32)    
    wrap()


smId= 0 
sm0 = rp2.StateMachine(smId, PioCounter)
sm0.put(0)              # init x
sm0.exec("pull()")
sm0.exec("mov(x, osr)") # 
sm0.put(62_500_000)     # loop counter 2 per second @ 125 MHz
#sm0.put(3125000)     # loop counter 4 per second
#sm0.put(6_250_000)     # loop counter 20 per second
#sm0.put(625_000)       # loop counter 200 per second



def dmaCount(count:int | None = None ):
    if( count is not None):
        dma.registers[2] = count
    return dma.registers[2]

def dmaBusy():
    return (dma.registers[3] & (1<<24)) > 0 

def dmaIrqHandler(dma):
    print(f"Dma Irq {dma} {dmaCount()} {[nice(x) for x in buffer]}")

dma = rp2.DMA()
dma.irq(dmaIrqHandler)
rawBuffer  = array('L',[0]*32)
buffer = memoryview(rawBuffer)
sm0.active(1)
loops = 0

def nice(counter):
    if( counter == 0 ):
        return 0

    return (0xffff_ffff - counter)

def startDma():
    global buffer
    dmaCountWords = 16

    control = dma.pack_ctrl(
        inc_read = 0, 
        ring_sel = 0,               # use write for ring
        treq_sel =  smId + 4,       # for state machine id 0..3
        irq_quiet = 0,         
        inc_write = 1,              
        ring_size = 0,         
        size = 2                    # 4 byte words
        )

    print(f"control = {control:X}")

    dma.config(read= PIO0_BASE + PIO_RXF0 + smId * 4 , write = addressof(rawBuffer),count=dmaCountWords, ctrl =control )
    # just a demo
    values = dma.unpack_ctrl(control)    
    print(values)
    
    dma.active(1)
    cnt = dmaCount()      
    print(f"start dma : cnt={cnt}")
    
    return cnt    

def readDmaSingleBlock():
        
    startDma()
    while(True):
        cnt = dmaCount()
        busy = dmaBusy()
        time.sleep(1)
        print(f"cnt = {cnt:x} busy = {busy} buffer = ", [ nice(x) for x in buffer])                            
        if( cnt == 0 ): 
            # option: restart if finished
            dma.registers[1] = addressof(rawBuffer)
            dmaCount(len(buffer))
            dma.active(1)
            #break                        

try:
    readDmaSingleBlock()       
except KeyboardInterrupt:
    pass

sm0.active(0)
dma.active(0)
dma.irq(None)
sm0.irq(None)
rp2.PIO(0).irq(None)






