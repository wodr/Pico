import rp2
from machine import mem32
from array import array
import struct 
import sys
from uctypes import addressof
from StateMachineHelper import ResetStatemachines,AddCyw43

_ADR_PIO0_BASE = const(0x50200000)
_ADR_PIO1_BASE = const(0x50300000)
_ADR_PIO1_OFFSET = _ADR_PIO1_BASE-_ADR_PIO0_BASE
_OFF_SM_START = const(0xC8)
_SIZE_SM = const(0xe0 - 0xC8)
_SMx_ADDR = const(0xd4-0xc8)


def BitVal(val,highestBit,lowestBit):
    """
     x, 32:8
    """
    return (val >> lowestBit) & ((1<<(highestBit-lowestBit+1))-1)

def PioAddress(pioNo):
    return _ADR_PIO0_BASE + pioNo  * _ADR_PIO1_OFFSET

def SMAddress(pioNo,smNo):
    adr = PioAddress(pioNo)+_OFF_SM_START+(smNo*_SIZE_SM)+_SMx_ADDR
    return (adr,mem32[adr])


def PioInfo(pioNo=0,infoLevel=0xFFFF):
    print(f"#####  PIO {pioNo} #####")
    pioBase = PioAddress(pioNo)
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

def SmInfo(smId):
    pioNo = smId // 4
    i = smId & 0x3     
    pioBase = PioAddress(pioNo)
    ctrl = mem32[pioBase]
    enabled = 1 if (ctrl & (1<<i))  else 0
    print(f" ===  SM{smId} PIO{pioNo} ENABLE={enabled}  ===  ")
    if( not enabled and False):
        return
    clkdiv = mem32[pioBase+i*_SIZE_SM+0xC8]
    print(f" {0xC8+i*_SIZE_SM:03X}: {clkdiv:08X} SM{smId}_CLKDIV           INTDIV        = {BitVal(clkdiv,31,16)} FRAC        = {BitVal(clkdiv,15,8)}")        
    execCtrl = mem32[pioBase+i*_SIZE_SM+0xCC]
    wrapTop = BitVal(execCtrl,16,12)
    wrapBottom = BitVal(execCtrl,11,7)
    print(f" {0xCC+i*_SIZE_SM:03X}: {execCtrl:08X} SM{smId}_EXECCTRL[31:19]  EXEC_STALLED  = {BitVal(execCtrl,31,31)} SIDE_EN     = {BitVal(execCtrl,30,30)} SIDE_PINDIR = {BitVal(execCtrl,29,29):>2} JMP_PIN      = {BitVal(execCtrl,28,24):>2} OUT_EN_SEL = {BitVal(execCtrl,23,19):>2}") 
    print(f" {0xCC+i*_SIZE_SM:03X}: {execCtrl:08X} SM{smId}_EXECCTRL[18:0]   INLINE_OUT_EN = {BitVal(execCtrl,18,18)} OUT_STICKY  = {BitVal(execCtrl,17,17)} WRAP_TOP    = {BitVal(execCtrl,16,12):02X} WRAP_BOTTOM  = {BitVal(execCtrl,11,7):02X} STATE_SEL  = {BitVal(execCtrl,4,4):>2} STATUS_N = {BitVal(execCtrl,3,0)}")
    shiftCtrl = mem32[pioBase+i*_SIZE_SM+0xD0]
    print(f" {0xD0+i*_SIZE_SM:03X}: {shiftCtrl:08X} SM{smId}_SHIFTCTRL[31:20] FJOIN_RX      = {BitVal(shiftCtrl,31,31)} FJPOIN_TX   = {BitVal(shiftCtrl,30,30)} PULL_THRESH = {BitVal(shiftCtrl,29,25):>2} PUSH_THRESH  = {BitVal(shiftCtrl,24,20):>2}")
    print(f" {0xD0+i*_SIZE_SM:03X}: {shiftCtrl:08X} SM{smId}_SHIFTCTRL[19:0]  OUT_SHIFTDIR  = {BitVal(shiftCtrl,19,19)} IN_SHIFTDIR = {BitVal(shiftCtrl,18,18)} AUTOPULL    = {BitVal(shiftCtrl,17,17):>2} AUTOPUSH     = {BitVal(shiftCtrl,16,16):>2}")
    pinCtrl = mem32[pioBase+i*_SIZE_SM+0xDC]
    print(f" {0xDC+i*_SIZE_SM:03X}: {pinCtrl:08X} SM{smId}_PINCTRL          SIDESET_COUNT = {BitVal(pinCtrl,31,29)} SET_COUNT   = {BitVal(pinCtrl,28,26)} OUT_COUNT   = {BitVal(pinCtrl,25,20):>2} SIDESET_BASE  = {BitVal(pinCtrl,14,10)} SET_BASE = {BitVal(pinCtrl,9,5)} OUT_BASE = {BitVal(pinCtrl,4,0):>2}")

    addr = mem32[pioBase+i*_SIZE_SM+0xD4]
    print(f" {0xD4+i*_SIZE_SM:03X}: {addr:08X} SM{smId}_ADDR             PC            = {BitVal(addr,4,0):02X}")
    instr = mem32[pioBase+i*_SIZE_SM+0xD8]
    si = Disasm(instr)
    print(f" {0xD8+i*_SIZE_SM:03X}: {instr:08X} SM{smId}_INSTR            INSTR         = {BitVal(instr,15,0):04X}              DISASM      = {si}")
    
    if( wrapTop != 31 or wrapBottom != 0):
        # assume Sm does not use all the prio instruction memory.
        
        DumpInstructions(pioNo,wrapBottom,wrapTop)

def DumpMemory(adr,len):
    for j in range(0,len,32):
        sys.stdout.write(f"{adr+j:08X} : ")
        for i in range(0,32,4):
            val = mem32[adr+j+i]
            if( val < 0 ):
                #print(f"{val:08X} {-val:08X}")
                val   = -val
                
            sys.stdout.write(f"{val:08X} ")
        print("")

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
    nop()  # 10
    nop()
    nop()
    nop()
    nop()
    nop()  # 15
    nop()
    nop()
    nop()
    nop()
    nop()  # 20    
    nop()
    nop()
    nop()
    nop()
    nop()  # 25
    nop()
    nop()
    nop()
    nop()
    nop()  # 30
    nop()
    nop()  # 32    
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
   

def AddProgram(smId):    
    global sm0
    sm0 = rp2.StateMachine(smId, PioCounter)
    sm0.put(0)              # init x
    sm0.exec("pull()")
    sm0.exec("mov(x, osr)") # 
    sm0.put(6_250_000)      # loop counter 20 per second
    sm0.active(1)
    return sm0

def Disasm(instr):
    """
    rudimentary disasembler for PIO instructions
    not ment to be complete now
    """
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
        
    if( sopcode == 'WAIT'):
        destinations = {
            0b000:'GPIO',
            0b001:'PIN',
            0b010:'IRQ',
            0b011:'RES',
            0b100:'GPIO',
            0b101:'PIN',
            0b110:'IRQ',
            0b111:'RES',}
        sdest = sources[BitVal(instr,6,5)]
        ssource += f",{BitVal(instr,7,7)}"
        
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
        # ssource = f"'{ssource}'" # make label

    sdest = destinations[BitVal(instr,7,5)]    
    if( sopcode == "PUSH/PULL"):
        sopcode = "PULL" if ( BitVal(instr,7,7) > 0 ) else "PUSH"
        sdest = "block" if( BitVal(instr,5,5) > 0 ) else "nonblock"
        ssource = ""

    return f"{sopcode}({sdest},{ssource})"
    

def DumpInstructions(pio,start=0,end=31):
    """ Read instructions from memory by using 
    
        set(x,ADDR)

        mov(pc,x)
    
    The PC is loaded from register X and the instruction register is filled 
    with the instruction from PIO memory at address X.
    Any statemachine can be used to execute this instruction 
    to read all memeroy from the PIO the statemachine belongs to.
    
    """
    # use any sm from that pio, just to execute the instructions. 
    # the sm should not be used, but can be, because X is modified.
    smId = 3     
    
    end +=1 # wrap target is the last included address so add 1
    sm = rp2.PIO(pio).state_machine(smId)        
    wasActive = sm.active()
    sm.active(0)
    pioBase = _ADR_PIO0_BASE + pio * 0x100000
    
    smId = smId & 0x3
    # print(f"Pio = {pio} pioBase = {pioBase:08X}")
    c = rp2.asm_pio_encode("nop()",0)
    
    for i in range(start,end,1):
        
        sm.exec(f"set(x,{i})")
        sm.exec(f"mov(pc,x)")
        addr = mem32[pioBase+smId*_SIZE_SM+ 0x0d4]
        instr = mem32[pioBase+smId*_SIZE_SM+0xD8]
        dc = Disasm(instr)
        print(f"  {i:02X} {addr:04x}: {instr:04X}  {dc:20}  func = {BitVal(instr,15,13):03b} side = {BitVal(instr,12,8):05b} 7:5 = {BitVal(instr,7,5):03b} 4:0 {BitVal(instr,4,0):05b} ")

    if( wasActive):
        sm.active(wasActive)

    #pwm = PwmHighResolution.PwmHighResolution(16,maxCount=50000,stateMachineIndex=3)
def TestCreateNop():
    instr = rp2.asm_pio_encode("set(x,1)",0)
    b = array('H',[instr,instr,instr,instr])    
    #program = struct.pack("IBB",addressof(b),len(b),-1)
    #sm = rp2.StateMachine(0,instructions)
    rp2.PIO(0).add_program((b,0,0,0,0,0,0,0)) # OK Works
    # DumpInstructions(0)
    PioInfo(0)

def TestNoOp(pio=0):
    print(NopProgram)
    ResetStatemachines()
    rp2.PIO(pio).add_program(NopProgram)
    #rp2.PIO(1).add_program(NopProgram)
    

#TestNoOp(0)
#TestNoOp(1)
#DumpInstructions(0)
DumpInstructions(1)
PioInfo(1)
    
    