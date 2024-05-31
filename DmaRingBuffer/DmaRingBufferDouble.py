import time
from array import array
import rp2
from uctypes import addressof
import StateMachineHelper

if 1==2:
    from ..Common.StateMachineHelper import *

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
    
    return (0xffff_ffff - counter)

class DmaRingBuffer: 
    # as long as count > 0 dma continues to write to the buffer
    # count can by any number, so set it to maximum before dma signal ready
    _MAXDMACOUNT = const(0xFFFFFFFF)
    #_MAXDMACOUNT = const(73)

    def __init__(self,numberOfBytes:int) -> None:
        """
        @Parameter
        ----------
        countBytesAsPowerOf2: size of the ringbuffer = 1<<countBytesAsPowerOf2 bytes

        Examples for :
        - 7 = 128 bytes
        - 6 = 64  bytes
        - 5 = 32 bytes
        """
        self.dma_data = rp2.DMA()
        self.dma_control = rp2.DMA()
        self.rawBuffer  = array('L',[0]*(self.numberOfBytes//4) ) 
        self.buffer = memoryview(self.rawBuffer)
        self.controlBuffer = array('L',[0]*8)
        
            
    
        
    def Stop(self):
        self.dma_data.active(0)

    def _dmaCount(self, count:int | None = None ) -> int:
        """
        returns the count of word written 
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

    def _dmaBusy(self):
        return (self.dma_data.registers[3] & (1<<24)) > 0 

    def _alignAddress(self,arraylike,mask): 
        """
        returns the pointer inside an array, that is aligned so, 
        that it can be used for wrapping by the dma logic
        start of buffer = addr & mask 
        """
        adr = addressof(arraylike)
        remainder = adr & mask
        if( remainder == 0) :
            return (adr,0)
        byteOffset = (mask+1) - remainder
        adr = adr + byteOffset        
        return (adr,byteOffset)

    def Start(self,stateMachineId:int):
                
        # 1<< ringSize is the number of bytes written before wrapped                
        alignedAddressOfBuffer,byteOffset = self._alignAddress(self.controlBuffer,3)

        alignedControlBuffer = memoryview(self.controlBuffer)
        alignedControlBuffer = alignedControlBuffer[bytearray//4]
        
        print(f"buffer = {addressof(self.controlBuffer):08X} aligned = {alignedAddressOfBuffer:08X} offset={byteOffset} size = {len(self.controlBuffer)} {[nice(x) for x in self.buffer]}")

        # use alias 1 write address and transcount

        alignedControlBuffer[0] = addressof(self.buffer)
        alignedControlBuffer[1] = len(self.buffer)*4
        
        controlControl = self.dma_control.pack_ctrl(
            inc_read = 1, 
            ring_sel = 1,                       # use write for ring
            treq_sel =  stateMachineId + 4,     # for state machine id 0..3
            irq_quiet = 1,         
            inc_write = 1,              
            ring_size = 3,                      # 8 bytes is this the size in bytes
            size = 2                            # 4 byte words
            count = len(addresses_of_data),
            )

        controlData = self.dma_data.pack_ctrl(
            inc_read = 0, 
            ring_sel = 0,                       # use write for ring
            treq_sel =  stateMachineId + 4,     # for state machine id 0..3
            irq_quiet = 1,         
            inc_write = 1,              
            ring_size = 0
            size = 2                            # 4 byte words            
            chain_to = self.dma_control.channel
            )


        print(f"address of buffer {alignedAddressOfBuffer:8X} {addressof(self.rawBuffer):8X}")

        self.dma_data.config(read= PIO0_BASE + PIO_RXF0 + stateMachineId * 4 , write = self.buffer,count=8, ctrl = controlData)
        # control channel has to set the write address ( was incremented ) trans count (was count down)  
        # this should then enable the channel to continue
        #                  0             1           2           3
        # Alias 0: 0    READ_ADDR    WRITE_ADDR  TRANS_COUNT     CTRL
        # Alias 1: 4    CTRL         READ_ADDR   WRITE_ADDR      TRANS_COUNT
        # Alias 2: 8    CTRL         TRANS_COUNT READ_ADDR       WRITE_ADDR
        # Alias 3: 12   CTRL         WRITE_ADDR  TRANS_COUNT     READ_ADDR
        self.dma_control.config(read= alignedControlBuffer , write = self.dma_data.registers[1] ,count=8, ctrl =controlControl )
        
        print(f"controlControl = {self.dma_data.unpack_ctrl(controlControl)}")
        print(f"controlDate = {self.dma_data.unpack_ctrl(controlData)}")
        
        self.dma_data.active(1)
        self.dma_control.active(1)
        count = self._dmaCount()      
        write = self._dmaWrite()   
        print(f"start dma : write={write:x} count={count:,}")
                
    def Get(self):
        """
            iterator, waits until at least one value is added to the dma.            
            yields a memoryview to the dma containing the values not read so far.            
        """
        lastRead = _MAXDMACOUNT- self._dmaCount()  
        lastCount = 0     
        fullWrite = 0
        # mask in words size (4 bytes)
        mask = self.mask>>2
        while(True):           
            cnt = self._dmaCount()  
            # print(f" dmaCount = {cnt}")
            if( cnt == 0 ):          
                # restart dma,
                # values might be lost: write is not possible while cnt = 0                 
                self._dmaCount(_MAXDMACOUNT)
                self.dma_data.active(1)   
            
            # only read this once to be consistent
            write  = _MAXDMACOUNT - cnt + fullWrite
                        
            count = cnt - lastCount 
            # keep polling or return empty
            
            if( write - lastRead > len(self.buffer)):                
                print(f"**** OVERFLOW **** count={count} lr={lastRead} w={write} cnt={cnt}")
                lastRead = write
                continue

            w  = write & mask
            r = lastRead & mask
            
            if( lastRead == write):
                 # yield (self.buffer[r:r],lastRead,write) # return empty buffer
                 continue            

            # print(f" {write} {w} {lastCount} {r}  {self._dmaWrite():08X}")
            if( w <= r): # needs wrap?
                wrapCount = len(self.buffer)-r                
                yield (self.buffer[r:],lastRead,lastRead+wrapCount)
                lastRead +=wrapCount        
                r = 0  

            if ( r != w):
                # any data left after wrap?
                yield (self.buffer[r:w],lastRead,write)
            
            lastRead = write
            if( cnt ==  0 ):
                fullWrite +=_MAXDMACOUNT

if __name__ == '__main__' :
    import random
    dma = DmaRingBuffer(7)
    dma.Start(smId)
    sm0.active(1)    
    print(f"count word = {dma.countBytes}")
    print("Delay   Read   Write   Count   Data")
    try:
        lastValue = -1
        slp = 0
        for v,r,w in dma.Get():                      
            print(f"{slp:>1.2f}    {r:>4}    {w:>4}    {w-r:>4}   {[nice(x) for x in v]}")                    
            
            # simulate other processing, while dma is filled             
            slp = (random.randint(1,10)/20)
            time.sleep(slp)

    except KeyboardInterrupt:
        pass

    sm0.active(0)
    dma.Stop()


