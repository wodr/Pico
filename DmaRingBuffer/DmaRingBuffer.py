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

smId= 0 
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
    _MAXDMACOUNT = const(0x4FFFFFFF)
    #_MAXDMACOUNT = const(73)

    def __init__(self,countBytesAsPowerOf2:int) -> None:
        """
        @Parameter
        ----------
        count32BitwordsAsPowerOf2: size of the ringbuffer size = 4 * 1<<count32BitwordsAsPowerOf2 bytes
        """
        self.dma = rp2.DMA()
        self.count32BitwordsAsPowerOf2 =countBytesAsPowerOf2
        self.countBytes = 1<<countBytesAsPowerOf2                
        self.mask = (1<<countBytesAsPowerOf2)-1
        # make the buffer so large, that worst case address alignment is possible
        # wrap in dma is implemented as masking the lower bits e.g 3FF, for 1024 words
        self.rawBuffer  = array('L',[0]*(self.countBytes//4 * 2) ) 
        self.buffer = memoryview(self.rawBuffer)
        
            
    def Start(self,stateMachineId:int):
        
        self._startDma(stateMachineId)

    def Stop(self):
        self.dma.active(0)

    def _dmaCount(self, count:int | None = None ) -> int:
        """
        returns the count of word written 
        """
        if( count is not None):
            self.dma.registers[2] = count
        return self.dma.registers[2]

    def _dmaWrite(self, write:int | None = None ) -> int:
        """
        returns the words written
        """
        if( write is not None):
            self.dma.registers[1] = write
        return self.dma.registers[1]

    def _dmaBusy(self):
        return (self.dma.registers[3] & (1<<24)) > 0 

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

    def _startDma(self,stateMachineId):
                
        # 1<< ringSize is the number of bytes written before wrapped                
        alignedAddressOfBuffer,byteOffset = self._alignAddress(self.rawBuffer,self.mask)
        self.buffer = self.buffer[byteOffset//4:byteOffset//4+self.countBytes//4]   # adjust memory view so that the start is aligned with the dma buffer        

        print(f"buffer = {addressof(self.rawBuffer):08X} aligned = {alignedAddressOfBuffer:08X} offset={byteOffset} size = {len(self.buffer)} {[nice(x) for x in self.buffer]}")

        #buffer =buffer[0:dmaCountWords]
        #print([x  for x in buffer])

        control = self.dma.pack_ctrl(
            inc_read = 0, 
            ring_sel = 1,                       # use write for ring
            treq_sel =  stateMachineId + 4,     # for state machine id 0..3
            irq_quiet = 1,         
            inc_write = 1,              
            ring_size = self.count32BitwordsAsPowerOf2,     # is this the size in bytes?       
            size = 2                            # 4 byte words
            )

        print(f"control = {control:X} address of buffer {alignedAddressOfBuffer:8X} {addressof(self.rawBuffer):8X}")

        self.dma.config(read= PIO0_BASE + PIO_RXF0 + stateMachineId * 4 , write = alignedAddressOfBuffer,count=_MAXDMACOUNT, ctrl =control )
        # just a demo
        values = self.dma.unpack_ctrl(control)    
        print(values)
        
        self.dma.active(1)
        count = self._dmaCount()      
        write = self._dmaWrite()   
        print(f"start dma : write={write:x} count={count}")
                
    def Get(self):
        """
            iterator, waits until at least one value is added to the dma.            
            yields a memoryview to the dma containing the values not read so far.            
        """
        lastRead = _MAXDMACOUNT- self._dmaCount()  
        lastCount = 0     
        # mask in words size (4 bytes)
        mask = self.mask>>2
        while(True):           
            cnt = self._dmaCount()  
            # print(f" dmaCount = {cnt}")
            if( cnt == 0 ):          
                # restart dma
                print("restart")
                # todo implement correct restart logic
                self._dmaCount(_MAXDMACOUNT)
                self.dma.active(1)   
            
            write  = _MAXDMACOUNT - cnt
                        
            count = cnt - lastCount 
            # keep polling or return empty
            if( lastRead == write):
                 # return 0 0 0?
                 continue
            
            if( write - lastRead > len(self.buffer)):                
                print(f"**** OVERFLOW **** count={count} lr={lastRead} w={write} cnt={cnt}")
                lastRead = write
                continue

            w  = write & mask
            r = lastRead & mask
            print(f" {write} {w} {lastCount} {r}  {self._dmaWrite():08X}")
            if( w <= r):
                # needs wrap?
                yield (self.buffer[r:],lastRead,write)
                r = 0  

            if ( r != w):
                # any data left after wrap?
                yield (self.buffer[r:w],lastRead,write)
            
            lastRead = write
            

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


