import time
from array import array
import rp2
from uctypes import addressof
from StateMachineHelper import ResetStatemachines
from machine import mem32 
import sys
if 1==2:
    from ..Common.StateMachineHelper import *

PIO0_BASE = const(0x50200000)
PIO_RXF0 = const(0x20)
_DMA_BASE = const(0x50000000)
_DMA_CHANNEL_ABORT = const(0x444)
_CH0_DBG_TCR = const(0x804)

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
#sm0.put(6_250_000)     # loop counter 20 per second
sm0.put(625_000)       # loop counter 200 per second

def nice(counter):
    #return hex(counter)
    if( counter == 0 ):
        return 0
    return counter
    #return (0xffff_ffff - counter)

class DmaRingBuffer: 
    # as long as count > 0 dma continues to write to the buffer
    # count can by any number, so set it to maximum before dma signal ready
    _MAXDMACOUNT = const(0xFFFFFFFF)
    #_MAXDMACOUNT = const(73)

    def __init__(self,countWords:int) -> None:
        """
        @Parameter
        ----------
        countBytesAsPowerOf2: size of the ringbuffer = 1<<countBytesAsPowerOf2 bytes

        Examples for :
        - 7 = 128 bytes
        - 6 = 64  bytes
        - 5 = 32 bytes
        """
        self.countBytes = countWords*4
        self.dma_data = rp2.DMA()
        self.dma_control = rp2.DMA()
        self.dma_control.active(0)
        self.dma_data.active(0)
        if( self._dmaError(self.dma_data) or self._dmaError(self.dma_control) ):
            self._abortDma()
        
       

        self.rawBuffer  = array('L',[0]*(self.countBytes//4) ) 
        self.buffer = memoryview(self.rawBuffer)
        self.controlBuffer = memoryview(array('L',[0]*8))
        
    def _abortDma(self):        
        abortMask = (1<< self.dma_control.channel) | (1<<self.dma_data.channel)
        print(f"*** aborting dma {self.dma_data.channel} and {self.dma_control.channel} ***")
        mem32[_DMA_BASE+ _DMA_CHANNEL_ABORT] = abortMask
        while( mem32[_DMA_BASE+ _DMA_CHANNEL_ABORT] != 0 ):
            time.sleep(0.1)
        
    def Stop(self):
        print(f"**** SHUTDOWN DMA ****")
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
        
    def _alignAddress(self,view: memoryview,countBytesAsPowerOf2:int) -> memoryview: 
        """
        assume memoryview has itemsize 4! 
        returns the pointer inside an array, that is aligned so, 
        that it can be used for wrapping by the dma logic
        buffer = addr & mask must be valid
        """
        adr = addressof(view)
        size = (1<<countBytesAsPowerOf2)
        mask = (size)-1
        
        # check alignment of buffer
        remainder = adr & mask
        byteOffset = ((mask+1) - remainder) & mask
        # print(f"size={size} mask={mask:x} align = {byteOffset&mask} adr = {adr:08X} => {adr+byteOffset:08X}")      
                
        # project the correct offset and size from memoryview
        return (view[byteOffset//4:byteOffset//4+size//4])

    def Start(self,stateMachineId:int):
                
        # 1<< ringSize is the number of bytes written before wrapped                
        
        self.controlBuffer = self._alignAddress(self.controlBuffer,3)
        

        print(f"buffer = {addressof(self.controlBuffer):08X}  size = {len(self.controlBuffer)} {[nice(x) for x in self.buffer]}")

        # use alias 3 write address as trigger
        
        controlControl = self.dma_control.pack_ctrl(
            inc_read = 0,                       # always read and write the same
            inc_write = 0,              
            ring_sel = 0,                       # use 1=write , 0=read for ring
            treq_sel =  0x3F ,                  # 
            irq_quiet = 1,                                         
            ring_size = 0,                      # online write 1 word
            size = 2                            # 4 byte words                        
            )


        # control channel has to set the write address ( was incremented ) trans count (was count down)  
        # this should then enable the channel to continue
        #                  0             1           2           3
        # Alias 0: 0    READ_ADDR    WRITE_ADDR  TRANS_COUNT     CTRL
        # Alias 1: 4    CTRL         READ_ADDR   WRITE_ADDR      TRANS_COUNT
        # Alias 2: 8    CTRL         TRANS_COUNT READ_ADDR       WRITE_ADDR
        # Alias 3: 12   CTRL         WRITE_ADDR  TRANS_COUNT     READ_ADDR
        controlData = self.dma_data.pack_ctrl(
            inc_read = 0, 
            inc_write = 1,              
            ring_sel = 0,                       # use 1=write , 0=read for ring
            treq_sel =  stateMachineId + 4 if stateMachineId < 4 else stateMachineId + 12 - 4,
            irq_quiet = 1,                      #             
            ring_size = 0,
            size = 2,                            # 4 byte words            
            chain_to = self.dma_control.channel
            )

        self.controlBuffer[0] = addressof(self.buffer[0:1])  # will be write_addr
        self.controlBuffer[1] = len(self.buffer)        # will be trans count
        
        print(f"len of data ={len(self.buffer)} len of control = {len(self.controlBuffer)} write/tran = {addressof(self.dma_data.registers[1:3]):08X}")
        self.dma_control.config(read= self.controlBuffer , write = self.dma_data.registers[11:12] ,count=1, ctrl =controlControl ) # use write t don't increment
        self.dma_data.config(read= PIO0_BASE + PIO_RXF0 + stateMachineId * 4 , write = self.buffer,count=len(self.buffer), ctrl = controlData)
        if( self._dmaError(self.dma_control) or self._dmaError(self.dma_control)):
            self._abortDma()

        self.Dump()
        #print(f"controlControl = {self.dma_data.unpack_ctrl(controlControl)}")
        #print(f"controlDate = {self.dma_data.unpack_ctrl(controlData)}")
                
        self.dma_data.active(1)
        #self.dma_control.active(1)
        #dma.dma_control.irq(self._dmaIrqHandler)

        #self.Dump()
        count = self._dmaTransCount()      
        write = self._dmaWrite()   
        print(f"start dma : write={write:x} count={count:,}")
    
    def Dump(self):
        print("            READ_ADDR  WRITE_ADDR    TRAN_COUNT  CH0_DBG_TCR ADR(buffer)    DATA[0]      DATA[1] " )
        data = [f"{x:08X}" for x in self.buffer[0:2] ]
        print(f"DATA({self.dma_data.channel:02})     {self.dma_data.registers[0]:08X}    {self.dma_data.registers[1]:08X}    {self.dma_data.registers[2]:>10} {mem32[_DMA_BASE+_CH0_DBG_TCR+self.dma_data.channel*0x40]:>10}    {addressof(self.buffer):08X}    {self.buffer[0]:08X}     {self.buffer[1]:08X}");
        print(f"CTRL({self.dma_control.channel:02})     {self.dma_control.registers[0]:08X}    {self.dma_control.registers[1]:08X}    {self.dma_control.registers[2]:>10} {mem32[_DMA_BASE+_CH0_DBG_TCR+self.dma_control.channel*0x40]:>10}    {addressof(self.controlBuffer):08X}    {self.controlBuffer[0]:08X}     {self.controlBuffer[1]:08X}");
        print(f"DATA({self.dma_data.channel:02})     {self.dma_data.unpack_ctrl(self.dma_data.ctrl)}")
        print(f"CTRL({self.dma_control.channel:02})     {self.dma_control.unpack_ctrl(self.dma_control.ctrl)}")
        print(f"data({len(self.buffer)})   = {[nice(x) for x in self.buffer]}")
        print(f"control({len(self.controlBuffer)}) = {[hex(x) for x in self.controlBuffer]}")

    def Get(self):
        """
            iterator, waits until at least one value is added to the dma.            
            yields a memoryview to the dma containing the values not read so far.            
        """
        lastRead = 0  
        lastFill = 0
        lastWrite = 0
        size = len(self.buffer)
        
        while(True):           
            trans =  self._dmaTransCount()  
            #print(self.dma_control.unpack_ctrl(self.dma_control.ctrl))
            # print(f" dmaCount = {cnt}")
            
            if( trans == len(self.buffer) ):       
                #print("RESET")   
                #self.dma_data.registers[2] = 4
                pass
                # restart dma,
                # values might be lost: write is not possible while cnt = 0                                 
            #print(f"data({len(self.buffer)})   = {[nice(x) for x in self.buffer]}")
            #print(f"control({len(self.controlBuffer)}) = {[hex(x) for x in self.controlBuffer]}")
            # only read this once to be consistent
            
            fill = size - trans
            
            count = (fill + size -lastFill) % size
            # keep polling or return empty
            #sys.stdout.write(f"\r count={count}\n")
            if( count == 0 ):
                # might also be an overflow
                # or return empty buffer
                yield (self.buffer[0:0],lastRead,lastWrite)
                continue

            
            write  = count + lastWrite
            w  = write % len(self.buffer)
            r = lastRead % len(self.buffer)
                        
            #sys.stdout.write(f"\rtrans={trans} fill={fill}/{lastFill} count={count}  lr={lastRead} lc={lastWrite}  r={r}  w={write}  {[nice(x) for x in self.buffer]}  |\n")

            lastFill = fill
            
            if( write - lastRead > len(self.buffer)):                
                print(f"**** OVERFLOW **** count={fill} lr={lastRead} w={write} cnt={trans}")
                lastRead = write
                continue
            
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
    dma = DmaRingBuffer(256)
    dma.Start(smId)
    sm0.active(1)
    print(f"count word = {dma.countBytes//4}")
    start = time.time_ns()
    print("Time{ms]  Delay   Read   Write   Count   Data")
    
    def Read():        
        lastValue = -1
        slp = 0
        for v,r,w in dma.Get():                      
            now = time.time_ns() -  start             
            print(f"{now//1e6:12} {slp:>1.2f}    {r:>4}    {w:>4}    {w-r:>4}   {[nice(x) for x in v[0:4]]} ... {[nice(x) for x in v[-4:]]} ")                     #{[nice(x) for x in dma.buffer]}
            
            if( len(v) != 0 ):                                    
                if( lastValue != v[0]-1):
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
                #print("RESET") 
                #dma.dma_data.registers[1] = addressof(dma.buffer)
                #dma._dmaCount(4)  
                #dma.dma_data.active(1)
                pass
                
            
            time.sleep(0.5)

    try:
        Read() 
    except KeyboardInterrupt as k:
        sm0.active(0)
        dma.Stop()   # important to shut down other several dma are kept alive.     
    except Exception as e:
        print(e)
        sm0.active(0)
        dma.Stop()        
        


