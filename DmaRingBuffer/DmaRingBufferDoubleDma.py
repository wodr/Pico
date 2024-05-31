import time
from array import array
import rp2
from uctypes import addressof
from StateMachineHelper import ResetStatemachines
from machine import mem32 
import sys
if 1==2:
    # upload this file to pico, to use it from the root folder
    # here just for intellisense
    from ..Common.StateMachineHelper import *

PIO0_BASE = const(0x50200000)
PIO_RXF0 = const(0x20)
_DMA_BASE = const(0x50000000)
_DMA_CHANNEL_ABORT = const(0x444)
_CH0_DBG_TCR = const(0x804)
_DMA_REGISTER_LENGTH = const(0x40)
_DMA_SIZE32 = const(2)
ResetStatemachines()

@rp2.asm_pio(autopush=True,autopull=False, push_thresh=32)
def PioCounter():    
    pull(noblock)
    wrap_target()
    mov(y, osr)                 # y is delay    
    label("loop")               # delay 
    jmp(y_dec, "loop")    
    jmp(x_dec,"done")           # current counter value, each loop one less
    label("done")    
    mov(y,invert(x))
    in_(y,32)       
    wrap()    

smId= 3 
sm0 = rp2.StateMachine(smId, PioCounter)
sm0.put(0)              # init x
sm0.exec("pull()")
sm0.exec("mov(x, osr)") # 
#sm0.put(62_500_000)     # loop counter 2 per second @ 125 MHz
sm0.put(6_250_000)     # loop counter 20 per second
#sm0.put(625_000)       # loop counter 200 per second

def nice(counter):
    #return hex(counter)
    if( counter == 0 ):
        return 0
    return counter
    
class DmaRingBuffer: 
    
    def __init__(self,countWords:int) -> None:
        """
        @Parameter
        ----------
            countWords: size of the ringbuffer uint32
        """
        self.countBytes = countWords*4
        self.dma_data = rp2.DMA()
        self.dma_control = rp2.DMA()
        self.dma_control.active(0)
        self.dma_data.active(0)

        if( self._dmaError(self.dma_data) or self._dmaError(self.dma_control) ):
            self._abortDma()
        
        self.buffer = memoryview(array('L',[0]*(self.countBytes//4) ))
        self.controlBuffer = memoryview(array('L',[0]))
        
    def _abortDma(self):        
        abortMask = (1<< self.dma_control.channel) | (1<<self.dma_data.channel)
        # print(f"*** aborting dma {self.dma_data.channel} and {self.dma_control.channel} ***")
        mem32[_DMA_BASE+ _DMA_CHANNEL_ABORT] = abortMask
        while( mem32[_DMA_BASE+ _DMA_CHANNEL_ABORT] != 0 ):
            time.sleep(0.1)
        
    def Stop(self):
        # print(f"**** SHUTDOWN DMA ****")
        self._abortDma()        
        self.dma_data.active(0)
        self.dma_control.active(0)        
        self.dma_control.close()
        self.dma_data.close()
        

    def _dmaTransCount(self, count:int | None = None ) -> int:
        """
        returns the transfers remaining until halting
        """
        if( count is not None):
            self.dma_data.registers[2] = count
        return self.dma_data.registers[2]

    def _dmaWrite(self, write:int | None = None ) -> int:
        """
        returns the words written
        """
        if( write is not None):
            self.dma_data.registers[1] = write
        return self.dma_data.registers[1]

    def _dmaBusy(self,dma):
        return (dma.registers[3] & (1<<24)) > 0 
    
    def _dmaError(self,dma):
        return  (dma.registers[3] & ((1<<30)|(1<<29))) > 0         
        
    def Start(self,stateMachineId:int):
                
        self.controlBuffer = self.controlBuffer
        
        controlControl = self.dma_control.pack_ctrl(
            inc_read = 0,                       # always read and write the same
            inc_write = 0,              
            ring_sel = 0,                       # not used 1=write , 0=read for ring
            treq_sel =  0x3F ,                  # what is the best value?
            irq_quiet = 1,                                         
            ring_size = 0,                      # not used
            size = _DMA_SIZE32                  # 32 bits
            )


        # control channel has to reset the write address ( was incremented )
        # trans count is initialized with previous value
        # this should then enable the channel to continue
        # use alias 3 write address as trigger
        
        #                  0             1           2           3 (Trigger)
        # Alias 0: 0    READ_ADDR    WRITE_ADDR  TRANS_COUNT     CTRL
        # Alias 1: 4    CTRL         READ_ADDR   WRITE_ADDR      TRANS_COUNT
        # Alias 2: 8    CTRL         TRANS_COUNT READ_ADDR       WRITE_ADDR
        # Alias 3: 12   CTRL         WRITE_ADDR  TRANS_COUNT     READ_ADDR
        controlData = self.dma_data.pack_ctrl(
            inc_read = 0, 
            inc_write = 1,              
            ring_sel = 0,                       # not used ,  1=write , 0=read for ring
            treq_sel =  stateMachineId + 4 if stateMachineId < 4 else stateMachineId + 12 - 4,
            irq_quiet = 1,                      #             
            ring_size = 0,
            size = _DMA_SIZE32,                 # 32 bits
            chain_to = self.dma_control.channel
            )

        self.controlBuffer[0] = addressof(self.buffer)     # will be write_addr        
        
        print(f"len of data ={len(self.buffer)} len of control = {len(self.controlBuffer)} write = {addressof(self.dma_data.registers[11:12]):08X}")
        self.dma_control.config(read= self.controlBuffer , write = self.dma_data.registers[11:12] ,count=len(self.controlBuffer), ctrl =controlControl ) 
        self.dma_data.config(read= PIO0_BASE + PIO_RXF0 + stateMachineId * 4 , write = self.buffer,count=len(self.buffer), ctrl = controlData)
        if( self._dmaError(self.dma_control) or self._dmaError(self.dma_control)):
            self._abortDma()

        self.Dump()
        #print(f"controlControl = {self.dma_data.unpack_ctrl(controlControl)}")
        #print(f"controlDate = {self.dma_data.unpack_ctrl(controlData)}")
                
        self.dma_data.active(1)
        
        #self.Dump()
        count = self._dmaTransCount()      
        write = self._dmaWrite()   
        print(f"start dma : write={write:x} count={count:,}")
    
    def Dump(self):
        print("            READ_ADDR  WRITE_ADDR    TRAN_COUNT  CH0_DBG_TCR ADR(buffer)    DATA[0]      DATA[1] " )
        
        print(f"DATA({self.dma_data.channel:02})     {self.dma_data.registers[0]:08X}    {self.dma_data.registers[1]:08X}    {self.dma_data.registers[2]:>10} {mem32[_DMA_BASE+_CH0_DBG_TCR+self.dma_data.channel*_DMA_REGISTER_LENGTH]:>10}    {addressof(self.buffer):08X}    {self.buffer[0]:08X}     {self.buffer[1]:08X}");
        print(f"CTRL({self.dma_control.channel:02})     {self.dma_control.registers[0]:08X}    {self.dma_control.registers[1]:08X}    {self.dma_control.registers[2]:>10} {mem32[_DMA_BASE+_CH0_DBG_TCR+self.dma_control.channel*_DMA_REGISTER_LENGTH]:>10}    {addressof(self.controlBuffer):08X}    {self.controlBuffer[0]:08X}     n/a");
        print(f"DATA({self.dma_data.channel:02})     {self.dma_data.unpack_ctrl(self.dma_data.ctrl)}")
        print(f"CTRL({self.dma_control.channel:02})     {self.dma_control.unpack_ctrl(self.dma_control.ctrl)}")
        print(f"data({len(self.buffer)})   = {[nice(x) for x in self.buffer[0:10]]}")
        print(f"control({len(self.controlBuffer)}) = {[hex(x) for x in self.controlBuffer]}")

    def Get(self):
        """
            iterator, current array of values (also empty)
            yields a memoryview to the dma containing the values not read so far.            
        """
        lastRead = 0  
        lastFill = 0
        lastWrite = 0
        size = len(self.buffer)
        
        while(True):           
            trans =  self._dmaTransCount()  
            
            fill = size - trans
            
            count = (fill + size -lastFill) % size
            
            # keep polling or return empty
            if( count == 0 ):
                # might also be an overflow
                # return empty buffer
                yield (self.buffer[0:0],lastRead,lastWrite)
                continue

            
            write  = count + lastWrite
            w  = write % len(self.buffer)
            r = lastRead % len(self.buffer)
                        
            #sys.stdout.write(f"\rtrans={trans} fill={fill}/{lastFill} count={count}  lr={lastRead} lc={lastWrite}  r={r}  w={write}  {[nice(x) for x in self.buffer]}  |\n")

            lastFill = fill
                        
            # print(f" {write} {w} {lastCount} {r}  {self._dmaWrite():08X}")
            if( w <= r): # needs wrap?                
                wrapCount = len(self.buffer)-r
                # print(f" wc = {wrapCount} lr = {lastRead} r =  {r} w = {w} trans={trans} fill={fill}")                
                yield (self.buffer[r:],lastRead,lastRead+wrapCount)
                lastRead +=wrapCount        
                r = 0  
                count -= wrapCount

            if ( r != w):
                # any data left after wrap?
                yield (self.buffer[r:w],lastRead,lastRead+count)
            
            lastRead += count
            lastWrite = write
            

if __name__ == '__main__' :
    import random
    dma = DmaRingBuffer(47)
    dma.Start(smId)
    sm0.active(1)
    print(f"count word = {dma.countBytes//4}")
    start = time.time_ns()
    print("   Time[ms]   Delay   Read   Write   Count   Data")
    
    def Read():        
        lastValue = -1
        slp = 0
        for v,r,w in dma.Get():                      
            now = time.time_ns() -  start             
            dp = f"{[nice(x) for x in v]}" if( len(v) < 16 ) else f"{[nice(x) for x in v[0:4]]} ... {[nice(x) for x in v[-4:]]}"
            print(f"{now//1e6:10}    {slp:>1.2f}    {r:>4}    {w:>4}    {w-r:>4} {dp}  ")
            
            if( len(v) != 0 ):                                    
                if( lastValue != v[0]-1 or len(v) != (w-r)):
                    print(f"**** ERROR *** {lastValue} {v[0]}")
            
                lastValue = v[-1]

            # simulate other processing, while dma is filled             
            slp = (random.randint(1,10)/20)
            #slp = 0.2
            time.sleep(slp)

    def Debug():
        while( True):
            dma.Dump()
            if( dma._dmaTransCount() == 0 ):                       
                pass
                
            
            time.sleep(0.5)

    try:
        Read() 
    except KeyboardInterrupt as k:
        print(k)

sm0.active(0)
dma.Stop()        
        


