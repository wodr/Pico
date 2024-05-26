import rp2
from machine import mem32
from array import array
import struct 
StateMachineFrequency  =  const(125_000_000)

ADR_PIO0_BASE = const(0x50200000)
ADR_PIO1_BASE = const(0x50300000)
ADR_SMx_FSTAT = const(0x50200000 + 0x004)
ADR_SMx_ADDR  = const(0x50200000 + 0x0D4)

OFF_INSTRUCTION_START = const(0x48)
OFF_SM_START = const(0xC8)
SIZE_SM = const(0xe0 - 0xC8)
SMx_ADDR = const(0xd4-0xc8)

def AnyAvailable(smNumber):
  return ((mem32[ADR_SMx_FSTAT + ((smNumber >> 2) << 20)] >> (8 + (smNumber & 3))) & 1) ^ 1

def PioAddress(pioNo):
    return ADR_PIO0_BASE + pioNo  * 0x100000

def SMAddress(pioNo,smNo):
    adr = PioAddress(pioNo)+OFF_SM_START+(smNo*SIZE_SM)+SMx_ADDR
    return (adr,mem32[adr])

def BitVal(val,highestBit,lowestBit):
    """
     x, 32:8
    """
    return (val >> lowestBit) & ((1<<(highestBit-lowestBit+1))-1)


def PioInfo(pioNo=0,infoLevel=0xFFFF):
    print(f"#####  PIO {pioNo} #####")
    pioBase = ADR_PIO0_BASE + pioNo * 0x100000        
    ctrl = mem32[pioBase]
    print(f"000: {ctrl:08X} CLKDIV_RESTART = {BitVal(ctrl,11,8)}  SM_RESTART = {BitVal(ctrl,7,5)}   SM_ENABLE = {BitVal(ctrl,3,0):04b}")
    fstat = mem32[pioBase+4]
    print(f"004: {fstat:08X} TXEMPTX ={BitVal(fstat,27,24)} TXFULL     ={BitVal(fstat,19,16)} TXEMPTY = {BitVal(fstat,11,8)} TXFULL = {BitVal(fstat,3,0)}")
    fdebug = mem32[pioBase+8]
    print(f"008: {fdebug:08X} TXSTALL = {BitVal(fdebug,27,24)} TXOVER = {BitVal(fdebug,19,16)} RXUNDE R= {BitVal(fdebug,11,8)} RXSTALL = {BitVal(fdebug,3,0)}")
    flevel = mem32[pioBase+0xc]    
    print(f"00C: {flevel:08X} RX3 = {BitVal(flevel,31,28)} TX3 = {BitVal(flevel,27,24)} RX2 = {BitVal(flevel,23,20)} TX2 = {BitVal(flevel,19,16)} RX1 = {BitVal(flevel,15,12)} TX1 = {BitVal(flevel,11,7)} RX0 = {BitVal(flevel,7,4)} TX0 = {BitVal(flevel,3,0)}")
    virq = mem32[pioBase+0x30]
    print(f"030: {virq:08X}")
    dbg_cfginfo = mem32[pioBase+0x44]    
    print(f"044: {dbg_cfginfo:08X} IMEM_SIZE = {BitVal(dbg_cfginfo,21,16)} SM_COUNT = {BitVal(dbg_cfginfo,11,8)} FIFO_DEPTH = {BitVal(dbg_cfginfo,5,0)}")
    
    for i in range(0,4):
        SmInfo(pioNo*4+i)

    return
    
    for i in range(0,4):
        enabled = (ctrl & (1<<i)) if 1  else 0
        smId = i+pioNo*4
        print(f" === SM{smId} EN={enabled} ===  ")
        if( not enabled and False):
            continue
        clkdiv = mem32[pioBase+i*SIZE_SM+0xC8]
        print(f"{0xC8+i*SIZE_SM:03X}: {clkdiv:08X} SM{smId}_CLKDIV      INT = {BitVal(clkdiv,31,16)} FRAC = {BitVal(clkdiv,15,8)}")        
        execCtrl = mem32[pioBase+i*SIZE_SM+0xCC]
        print(f"{0xCC+i*SIZE_SM:03X}: {execCtrl:08X} SM{smId}_EXECCTRL[31:19] EXEC_STALLED = {BitVal(execCtrl,31,31)} SIDE_EN = {BitVal(execCtrl,30,30)} SIDE_PINDIR = {BitVal(execCtrl,29,29)} JMP_PIN = {BitVal(execCtrl,28,24)} OUT_EN_SEL  = {BitVal(execCtrl,23,19)}") 
        print(f"{0xCC+i*SIZE_SM:03X}: {execCtrl:08X} SM{smId}_EXECCTRL[18:0]  INLINE_OUT_EN = {BitVal(execCtrl,18,18)} OUT_STICKY = {BitVal(execCtrl,17,17)} WRAP_TOP = {BitVal(execCtrl,16,12)} {BitVal(execCtrl,16,12):02X} WRAP_BOTTOM = {BitVal(execCtrl,11,7)} {BitVal(execCtrl,11,7):02X} STATE_SEL = {BitVal(execCtrl,4,4)} STATUS_N = {BitVal(execCtrl,3,0)}")
        shiftCtrl = mem32[pioBase+i*SIZE_SM+0xD0]
        print(f"{0xD0+i*SIZE_SM:03X}: {shiftCtrl:08X} SM{smId}_SHIFTCTRL[31:20] FJOIN_RX = {BitVal(shiftCtrl,31,31)} FJPOIN_TX = {BitVal(shiftCtrl,30,30)} PULL_THRESH = {BitVal(shiftCtrl,29,25)} PUSH_THRESH = {BitVal(shiftCtrl,24,20)}")
        print(f"{0xD0+i*SIZE_SM:03X}: {shiftCtrl:08X} SM{smId}_SHIFTCTRL[19:0]  OUT_SHIFTDIR = {BitVal(shiftCtrl,19,19)} IN_SHIFTDIR = {BitVal(shiftCtrl,18,18)} AUTOPULL = {BitVal(shiftCtrl,17,17)} AUTOPUSH = {BitVal(shiftCtrl,16,16)}")
        addr = mem32[pioBase+i*SIZE_SM+0xD4]
        print(f"{0xD4+i*SIZE_SM:03X}: {addr:08X} SM{smId}_ADDR {BitVal(addr,4,0)}")
        instr = mem32[pioBase+i*SIZE_SM+0xD8]
        print(f"{0xD8+i*SIZE_SM:03X}: {instr:08X} SM{smId}_INSTR {BitVal(instr,15,0):04X}")
        pinCtrl = mem32[pioBase+i*SIZE_SM+0xDC]
        print(f"{0xDC+i*SIZE_SM:03X}: {pinCtrl:08X} SM{smId}_PINCTRL  SIDESET_COUNT = {BitVal(pinCtrl,31,29)} SET_COUNT = {BitVal(pinCtrl,28,26)} OUT_COUNT = {BitVal(pinCtrl,25,20)} SIDESET_BASE = {BitVal(pinCtrl,14,10)} SET_BASE = {BitVal(pinCtrl,9,5)} OUT_BASE = {BitVal(pinCtrl,4,0)}")

def SmInfo(smId):
    pioNo = smId // 4
    i = smId & 0x3 
    smId = i+pioNo*4
    pioBase = ADR_PIO0_BASE + pioNo * 0x100000        
    ctrl = mem32[pioBase]
    enabled = (ctrl & (1<<i)) if 1  else 0
    print(f" === SM{smId} PIO={pioNo} ENABLE={enabled} ===  ")
    if( not enabled and False):
        return
    clkdiv = mem32[pioBase+i*SIZE_SM+0xC8]
    print(f"{0xC8+i*SIZE_SM:03X}: {clkdiv:08X} SM{smId}_CLKDIV           INTDIV        = {BitVal(clkdiv,31,16)} FRAC        = {BitVal(clkdiv,15,8)}")        
    execCtrl = mem32[pioBase+i*SIZE_SM+0xCC]
    print(f"{0xCC+i*SIZE_SM:03X}: {execCtrl:08X} SM{smId}_EXECCTRL[31:19]  EXEC_STALLED  = {BitVal(execCtrl,31,31)} SIDE_EN     = {BitVal(execCtrl,30,30)} SIDE_PINDIR = {BitVal(execCtrl,29,29):>2} JMP_PIN     = {BitVal(execCtrl,28,24):>2} OUT_EN_SEL = {BitVal(execCtrl,23,19):>2}") 
    print(f"{0xCC+i*SIZE_SM:03X}: {execCtrl:08X} SM{smId}_EXECCTRL[18:0]   INLINE_OUT_EN = {BitVal(execCtrl,18,18)} OUT_STICKY  = {BitVal(execCtrl,17,17)} WRAP_TOP    = {BitVal(execCtrl,16,12):02X} WRAP_BOTTOM = {BitVal(execCtrl,11,7):02X} STATE_SEL  = {BitVal(execCtrl,4,4):>2} STATUS_N = {BitVal(execCtrl,3,0)}")
    shiftCtrl = mem32[pioBase+i*SIZE_SM+0xD0]
    print(f"{0xD0+i*SIZE_SM:03X}: {shiftCtrl:08X} SM{smId}_SHIFTCTRL[31:20] FJOIN_RX      = {BitVal(shiftCtrl,31,31)} FJPOIN_TX   = {BitVal(shiftCtrl,30,30)} PULL_THRESH = {BitVal(shiftCtrl,29,25):>2} PUSH_THRESH = {BitVal(shiftCtrl,24,20):>2}")
    print(f"{0xD0+i*SIZE_SM:03X}: {shiftCtrl:08X} SM{smId}_SHIFTCTRL[19:0]  OUT_SHIFTDIR  = {BitVal(shiftCtrl,19,19)} IN_SHIFTDIR = {BitVal(shiftCtrl,18,18)} AUTOPULL    = {BitVal(shiftCtrl,17,17):>2} AUTOPUSH    = {BitVal(shiftCtrl,16,16):>2}")
    pinCtrl = mem32[pioBase+i*SIZE_SM+0xDC]
    print(f"{0xDC+i*SIZE_SM:03X}: {pinCtrl:08X} SM{smId}_PINCTRL          SIDESET_COUNT = {BitVal(pinCtrl,31,29)} SET_COUNT   = {BitVal(pinCtrl,28,26)} OUT_COUNT   = {BitVal(pinCtrl,25,20)} SIDESET_BASE  = {BitVal(pinCtrl,14,10)} SET_BASE = {BitVal(pinCtrl,9,5)} OUT_BASE = {BitVal(pinCtrl,4,0):>2}")

    addr = mem32[pioBase+i*SIZE_SM+0xD4]
    print(f"{0xD4+i*SIZE_SM:03X}: {addr:08X} SM{smId}_ADDR             PC            = {BitVal(addr,4,0):02X}")
    instr = mem32[pioBase+i*SIZE_SM+0xD8]
    si = Disasm(instr)
    print(f"{0xD8+i*SIZE_SM:03X}: {instr:08X} SM{smId}_INSTR            INSTR         = {BitVal(instr,15,0):04X}              DISASM      = {si}")
    DumpInstructions(pioNo,BitVal(execCtrl,11,7),BitVal(execCtrl,16,12))

def ResetStatemachines():
    for i in range(0,8):
        av = AnyAvailable(i)
        #print(f"available = {av}")
        try:
            #print(f"statemachine : {i} {rp2.StateMachine(i).active()}")
            rp2.StateMachine(i).active(0)
        except ValueError as e:
            #print(f"cannot stop statemachine {i}  {e}")
            pass

    rp2.PIO(0).remove_program() # reset all
    rp2.PIO(1).remove_program() # reset all
    rp2.PIO(0).irq(None)
    rp2.PIO(1).irq(None)
    for i in range(0,8):
        try:
            av = AnyAvailable(i)
            #print(f"available {i} = {av}")
            rp2.StateMachine(i).irq(None)
        except ValueError as e :
            pass
            #print(f"cannot remove irq for statemachine {i} {e}")

@rp2.asm_pio()
def NopProgram():
    wrap_target()
    nop()   # 1
    nop()
    nop()
    nop()
    nop()   # 5
    nop()
    nop()
    nop()
    nop()
    nop()
    wrap()


if __name__ == '__main__':
    #import PwmHighResolution 
    import sys
    from uctypes import addressof
    
    def Dump(adr,len):
        for j in range(0,len,32):
            sys.stdout.write(f"{adr+j:08X} : ")
            for i in range(0,32,4):
                val = mem32[adr+j+i]
                if( val < 0 ):
                    #print(f"{val:08X} {-val:08X}")
                    val   = -val
                    
                sys.stdout.write(f"{val:08X} ")
            print("")

    # HACK! make exactly the same program and load it to sm 4,
    # then managed pio reserves the memory and does not overwrite the 
    # cyw43 program memory
    @rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW,set_init=[rp2.PIO.OUT_LOW])
    def cyw32():
        wrap_target()
        label("lp")
        out(pins,1).side(0)
        jmp(x_dec,"lp")
        set(pindirs,0).side(0)
        nop().side(1)
        label("lp2")
        in_(pins,1).side(1)
        jmp(y_dec,"lp2").side(0)        
        wrap()

        
    @rp2.asm_pio(autopush=True,autopull=True, push_thresh=32)
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

    ResetStatemachines()
    global sm0
    def AddCYW32(smId):
        sm0 = rp2.StateMachine(smId, cyw32,set_base = 24, sideset_base =29, out_base = 24 )        
        SmInfo(smId)
        DumpInstructions(smId//4)
        return sm0

    def AddProgram(smId):    
        global sm0
        sm0 = rp2.StateMachine(smId, PioCounter)
        sm0.put(0)              # init x
        sm0.exec("pull()")
        sm0.exec("mov(x, osr)") # 
        #sm0.put(62_500_000)     # loop counter 2 per second @ 125 MHz
        sm0.put(6_250_000)     # loop counter 20 per second
        #sm0.put(625_000)       # loop counter 200 per second
        sm0.active(1)
        return sm0
    def Disasm(instr):

        opcode = BitVal(instr,15,13)
        opcodes = {
            0b000:'JMP',
            0b001:'WAIT',
            0b010:'IN',
            0b011:'OUT',
            0b100:'PUSH/PULL',            
            0b101:'MOV',
            0b110:'IRQ',
            0b111:'SET'}
        
        sopcode = opcodes[opcode]

        destinations = {
                0b000:'PINS',
                0b001:'X',
                0b010:'Y',
                0b011:'res',
                0b100:'EXEC',
                0b101:'PC',
                0b110:'ISR',
                0b111:'OSR'}
        sources = {
                0b000:'PINS',
                0b001:'X',
                0b010:'Y',
                0b011:'NULL',
                0b100:'RES',
                0b101:'STATUS',
                0b110:'ISR',
                0b111:'OSR'}

        ssource = f"{BitVal(instr,4,0):02X}"
        #ssource = sources[BitVal(instr,2,0)]

        if( sopcode == 'SET'):
            destinations[0b100]='PINDIRS'
        
        if( sopcode == 'MOV'):
            ssource = sources[BitVal(instr,2,0)]
                
        if( sopcode == 'JMP'):
            destinations= {
                0b000:'ALWAYS',
                0b001:'not_x',
                0b010:'x_dec',
                0b011:'not_y',
                0b100:'y_dec',
                0b101:'x_not_y',
                0b110:'PIN',
                0b111:'not_OSRE'}
            
            

        
        sdest = destinations[BitVal(instr,7,5)]
        
        
        return f"{sopcode}({sdest},{ssource})"
        

    def DumpInstructions(pio,start=0,end=31):
        
        
        #sm = AddProgram(smId)
        #sm = rp2.StateMachine(smId, NopProgram)
        smId = 1
        end +=1
        sm = rp2.PIO(pio).state_machine(smId)        
        
        pioBase = ADR_PIO0_BASE + pio * 0x100000
        
        smId = smId & 0x3
        print(f"pioBase = {pioBase:08X} smId={smId}")
        c = rp2.asm_pio_encode("nop()",0)
        
        for i in range(start,end,1):
            
            sm.exec(f"set(x,{i})")
            sm.exec(f"mov(pc,x)")
            addr = mem32[pioBase+smId*SIZE_SM+ 0x0d4]
            instr = mem32[pioBase+smId*SIZE_SM+0xD8]
            dc = Disasm(instr)
            print(f"{i:03} {addr:04x}: {instr:04X}  {dc:20}  func = {BitVal(instr,15,13):03b} side = {BitVal(instr,12,8):05b} 7:5 = {BitVal(instr,7,5):03b} 4:0 {BitVal(instr,4,0):05b} ")
    
    #pwm = PwmHighResolution.PwmHighResolution(16,maxCount=50000,stateMachineIndex=3)
    def TestCreateNop():
        instr = rp2.asm_pio_encode("set(x,1)",0)
        b = array('H',[instr,instr,instr,instr])
        instructions =[instr,instr,instr,instr]
        #program = struct.pack("IBB",addressof(b),len(b),-1)
        #sm = rp2.StateMachine(0,instructions)
        rp2.PIO(0).add_program((b,0,0,0,0,0,0,0)) # OK Works
        TestInstrRead(0)
        PioInfo(0)

    #TestInstrRead(5)
    #TestCreateNop()
    #DumpInstructions(1)
    AddCYW32(5)

    #print(NopProgram)
    def TestNoOp():
        adrNopProgram = id(NopProgram)
        w0 = mem32[adrNopProgram]
        adr1 = mem32[adrNopProgram+12]
        adr2 = mem32[adrNopProgram+16]
        print(f"prg = {adrNopProgram:x} {w0:08X} {adr1:08X} {adr2:08X}")    
        Dump(adrNopProgram,32)
        Dump(adr1,32)
        Dump(adr2,32)
        Dump(mem32[adrNopProgram],32)

# stack: 564 out of 7936
# GC: total: 191872, used: 96896, free: 94976
# No. of 1-blocks: 3353, 2-blocks: 224, max blk sz: 484, max free sz: 5924
# GC memory layout; from 20011280:
    
    print(mem32[0x21000000])
    # see https://github.com/raspberrypi/pico-sdk/blob/master/src/rp2_common/pico_standard_link/memmap_default.ld

    @micropython.viper
    def AdrOf(x)  -> int :
        adr = x
        print(adr)
        return 0
    #obj = rp2.StateMachine(0)
    obj = rp2.PIO(0)
    adr = id(obj)
    # pio :  10075E28 50200000 00000007 10075E28 50300000 00000009 100759BC 0000011D
    #adr = id(obj.add_program)
    #adr = 0x1006E8F8
    #adr = 0x1006FD64
    
    print(f"ADR SM0 {adr:08X}")

    s = adr-128
    l = 256
    #Dump(s,l)

    #PioInfo(0,1)
    #PioInfo(1,1)

    #AddProgram(5)    
    #AddProgram(1)
    #AddProgram(2)
    print("")
    #Dump(s,l)
    

    
    