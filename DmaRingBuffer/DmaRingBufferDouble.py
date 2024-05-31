import time
from array import array
import rp2
from uctypes import addressof
import StateMachineHelper
from machine import mem32 
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
    mov(y,invert(x))
    in_(y,32)       
    wrap()    

smId= 3 
sm0 = rp2.StateMachine(smId, PioCounter)
sm0.put(0)              # init x
sm0.exec("pull()")
sm0.exec("mov(x, osr)") # 
sm0.put(62_500_000)     # loop counter 2 per second @ 125 MHz
#sm0.put(6_250_000)     # loop counter 20 per second
#sm0.put(625_000)       # loop counter 200 per second

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
        self.rawBuffer  = array('L',[0]*(self.countBytes//4) ) 
        self.buffer = memoryview(self.rawBuffer)
        self.controlBuffer = memoryview(array('L',[0]*8))
        
            
    
        
    def Stop(self):
        self.dma_data.active(0)
        self.dma_control.active(0)
        self.dma_data.close()
        self.dma_control.close()

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

        # use alias 1 write address and transcount

        
        controlControl = self.dma_control.pack_ctrl(
            inc_read = 1, 
            inc_write = 1,              
            ring_sel = 1,                       # use 1=write , 0=read for ring
            treq_sel =  0x3F ,                  # for state machine id 0..3
            irq_quiet = 0,                                         
            ring_size = 3,                      # 8 bytes is this the size in bytes:  write_addr and trans_count
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
            treq_sel =  stateMachineId + 4,     # for state machine id 0..3
            irq_quiet = 1,                      #             
            ring_size = 0,
            size = 2,                            # 4 byte words            
            chain_to = self.dma_control.channel
            )

        self.controlBuffer[0] = addressof(self.buffer[0:1])  # will be write_addr
        self.controlBuffer[1] = len(self.buffer)        # will be trans count
        
        print(f"len of data ={len(self.buffer)} len of control = {len(self.controlBuffer)} write/tran = {addressof(self.dma_data.registers[1:3]):08X}")
        self.dma_control.config(read= self.controlBuffer , write = self.dma_data.registers[6:8] ,count=len(self.controlBuffer), ctrl =controlControl )
        self.dma_data.config(read= PIO0_BASE + PIO_RXF0 + stateMachineId * 4 , write = self.buffer,count=len(self.buffer), ctrl = controlData)
        self.Dump()
        #print(f"controlControl = {self.dma_data.unpack_ctrl(controlControl)}")
        #print(f"controlDate = {self.dma_data.unpack_ctrl(controlData)}")
                
        self.dma_data.active(1)
        dma.dma_control.irq(self._dmaIrqHandler)

        self.Dump()
        count = self._dmaCount()      
        write = self._dmaWrite()   
        print(f"start dma : write={write:x} count={count:,}")
    def _dmaIrqHandler(self,val):
        # reset the dma read pointer
        print(f"RESET COntrol channel {val}")
        #self.dma_control.registers[0] = addressof(self.controlBuffer)

    def Dump(self):
        print("            READ_ADDR  WRITE_ADDR    TRAN_COUNT  CH0_DBG_TCR ADR(buffer)    DATA[0]      DATA[1] " )
        data = [f"{x:08X}" for x in self.buffer[0:2] ]
        print(f"DATA({self.dma_data.channel:02})     {self.dma_data.registers[0]:08X}    {self.dma_data.registers[1]:08X}    {self.dma_data.registers[2]:>10} {mem32[0x50000000+0x804+self.dma_data.channel*0x40]:>10}    {addressof(self.buffer):08X}    {self.buffer[0]:08X}     {self.buffer[1]:08X}");
        print(f"CTRL({self.dma_control.channel:02})     {self.dma_control.registers[0]:08X}    {self.dma_control.registers[1]:08X}    {self.dma_control.registers[2]:>10} {mem32[0x50000000+0x804+self.dma_control.channel*0x40]:>10}    {addressof(self.controlBuffer):08X}    {self.controlBuffer[0]:08X}     {self.controlBuffer[1]:08X}");
        print(f"DATA({self.dma_data.channel:02})     {self.dma_data.unpack_ctrl(self.dma_data.ctrl)}")
        print(f"CTRL({self.dma_control.channel:02})     {self.dma_control.unpack_ctrl(self.dma_control.ctrl)}")
        print(f"data({len(self.buffer)})   = {[nice(x) for x in self.buffer]}")
        print(f"control({len(self.controlBuffer)}) = {[hex(x) for x in self.controlBuffer]}")

    def Get(self):
        """
            iterator, waits until at least one value is added to the dma.            
            yields a memoryview to the dma containing the values not read so far.            
        """
        lastRead = len(self.buffer) - self._dmaCount()  
        lastCount = 0     
        fullWrite = 0
        # mask in words size (4 bytes)
        
        while(True):           
            cnt = self._dmaCount()  
            print(self.dma_control.unpack_ctrl(self.dma_control.ctrl))
            # print(f" dmaCount = {cnt}")
            if( cnt == 0 ):       
                print("RESET")   
                #self.dma_data.registers[2] = 4
                pass
                # restart dma,
                # values might be lost: write is not possible while cnt = 0                                 
            #print(f"data({len(self.buffer)})   = {[nice(x) for x in self.buffer]}")
            #print(f"control({len(self.controlBuffer)}) = {[hex(x) for x in self.controlBuffer]}")
            # only read this once to be consistent
            write  = len(self.buffer) - cnt + fullWrite
                        
            count = cnt - lastCount 
            # keep polling or return empty
            
            if( write - lastRead > len(self.buffer)):                
                print(f"**** OVERFLOW **** count={count} lr={lastRead} w={write} cnt={cnt}")
                lastRead = write
                continue

            w  = write 
            r = lastRead
            
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
                lastRead = 0

if __name__ == '__main__' :
    import random
    dma = DmaRingBuffer(4)
    dma.Start(smId)
    sm0.active(1)    
    print(f"count word = {dma.countBytes//4}")
    print("Delay   Read   Write   Count   Data")
    def Read():
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

    def Debug():
        while( True):
            dma.Dump()
            if( dma._dmaCount() == 0 ):       
                #print("RESET") 
                #dma.dma_data.registers[1] = addressof(dma.buffer)
                #dma._dmaCount(4)  
                #dma.dma_data.active(1)
                pass
                
            
            time.sleep(0.5)

    try:
        Debug() 
    except Exception as e:
        print(e)
        sm0.active(0)
        dma.Stop()


