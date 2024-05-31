import rp2
from array import array
StateMachineFrequency  =  const(125_000_000)

def ResetStatemachines():
    
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
    # fill memory
    nops32 = [array('H', [40993] * 32), -1, 0, 16384, 0, None, None, None] # mov(x,x)
    rp2.PIO(0).add_program(nops32)
    rp2.PIO(0).remove_program()     # reset all
    # don't reset all on PIO(1), because memory use by cyw43 is also marked as unused.
    # remove a program from offset 0 with len 26, so don't touch the cyw43 program 
    nops = [array('H', [40993] * 26), -1, 0, 16384, 0, None, None, None] # mov(x,x)
    rp2.PIO(1).remove_program(nops)
    nops[2] = 0
    # nice to have:
    rp2.PIO(1).add_program(nops)    #  fill memory with nops
    rp2.PIO(1).remove_program(nops) #  remove them again
    rp2.PIO(0).irq(None)
    rp2.PIO(1).irq(None)
    
    for i in range(0,8):
        try:            
            rp2.StateMachine(i).irq(None)
        except ValueError as e :
            pass
            #print(f"cannot remove irq for statemachine {i} {e}")


if ( __name__ == '__main__'):
    from PioDebugger import DumpInstructions
    from array import array
      
    def CrashPio():
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
        ResetStatemachines()
        program[2] = -1 # not allocated yet
        rp2.StateMachine(7,program)
        print(program)   
        DumpInstructions(1) 


    #CrashPio()
    SaveRemoveProgram()
    #ResetStatemachines()

