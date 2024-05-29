import rp2
from PioDebugger import DumpInstructions
from array import array
    
StateMachineFrequency  =  const(125_000_000)

# steps to reproduce
#   program = [array('H', [41026, 41026, 41026, 41026, 41026]), -1, -1, 16384, 0, None, None, None]
#   rp2.StateMachine(7,program)
#   print(program) # => address is 21 to 25
#   rp2.PIO(1).remove_program()
#   set address to -1 
#   program[2] = -1
#   program = [array('H', [41026, 41026, 41026, 41026, 41026]), -1, -1, 16384, 0, None, None, None]
#   rp2.PIO(1).remove_program()
#   print(program)
#   [array('H', [41026, 41026, 41026, 41026, 41026]), -1, 27, 16384, 0, None, None, None]
#   program is no allocated at address 27 - 31 and overwrite the cyw32 program
def CrashPio():
    from PioDebugger import DumpInstructions
    from array import array
    program = [array('H', [41026, 41026, 41026, 41026, 41026]), -1, -1, 16384, 0, None, None, None]
    rp2.StateMachine(7,program)
    print(program)  # program is at address 21, because pio_add_program knows about used instruction memory
    DumpInstructions(1)
    rp2.PIO(1).remove_program()
    program[2] = -1 # not allocated yet
    rp2.StateMachine(7,program)
    print(program)   # now has offet 27 and overwrite cyw43 
    DumpInstructions(1) 

def SaveRemoveProgram():
    program = [array('H', [41026, 41026, 41026, 41026, 41026]), -1, -1, 16384, 0, None, None, None]
    rp2.StateMachine(7,program)
    print(program)
    DumpInstructions(1)
    SaveResetStatemachines()
    program[2] = -1 # not allocated yet
    rp2.StateMachine(7,program)
    print(program)   
    DumpInstructions(1) 

def SaveResetStatemachines():
    
    for i in range(0,8):
        # sm for is used by cyw43 driver
        if i == 4 :
            continue
        try:
            #print(f"statemachine : {i} {rp2.StateMachine(i).active()}")
            rp2.StateMachine(i).active(0)
        except ValueError as e:
            #print(f"cannot stop statemachine {i}  {e}")
            pass

    rp2.PIO(0).remove_program() # reset all
    # don't reset all on PIO(1), because memory use by cyw43 is also marked as unused.
    # remove a program from offset 0 with len 26, so don't touch the cyw43 program 
    nops = [array('H', [40993] * 25), -1, 0, 16384, 0, None, None, None] # mov(x,x)
    rp2.PIO(1).remove_program(nops)
    nops[2] = 0
    rp2.PIO(1).add_program(nops)    #  fill memory with nops
    rp2.PIO(1).remove_program(nops) #  remove them again
    rp2.PIO(0).irq(None)
    rp2.PIO(1).irq(None)
    print(Nop)
    for i in range(0,8):
        try:            
            rp2.StateMachine(i).irq(None)
        except ValueError as e :
            pass
            #print(f"cannot remove irq for statemachine {i} {e}")

#CrashPio()
#SaveRemoveProgram()
def Repro():
    program = [array('H', [41026, 41026, 41026, 41026, 41026]), -1, -1, 16384, 0, None, None, None]
    rp2.StateMachine(7,program)
    print(program)  # program is at address 21, because pio_add_program knows about used instruction memory
    rp2.PIO(1).remove_program()
    program[2] = -1 # not allocated yet, you could also use a new program
    rp2.StateMachine(7,program)
    print(program)   # now has offet 27 and overwrite cyw43 


def Dump():
    from machine import mem32
    _SIZE_SM = const(0xe0 - 0xC8)
    smId = 2    
    end = 32
    start = 0 
    pio  = 1
    sm = rp2.PIO(1).state_machine(smId)        
    pioBase = 0x50200000+ pio * 0x100000
    
    smId = smId & 0x3
    for i in range(start,end,1):
        
        sm.exec(f"set(x,{i})")
        sm.exec(f"mov(pc,x)")
        addr = mem32[pioBase+smId*_SIZE_SM+ 0x0d4]
        instr = mem32[pioBase+smId*_SIZE_SM+0xD8]

        print(f"  {i:02X} {addr:04x}: {instr:04X} ")

Dump()    