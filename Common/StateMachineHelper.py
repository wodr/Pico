import rp2
from machine import mem32
StateMachineFrequency  =  const(125_000_000)




# HACK! cyw32 program
@rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW,set_init=[rp2.PIO.OUT_LOW])
def cyw32_program():
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
    
def AddCyw43(smId: int) -> int:
    """
    Problem:
    -------
    If on pico w the network is enable the PIO 1 SM 4 is used by the driver.
    Because PIO python implementation does not know about the used memory,
    it will overwrite the pio instruction memory of the cyw43 PIO program.

    Workaround:
    ----------
    Create the same program and load it at exactly the same address 
    the cyw43 program resides. Then python PIO will mark this memory as used.
    
    How could this be done:

    The python PIO support always stores programs from the highest address (TOP)
    to the lowest (BOTTOM).
    The cyw43 program occupies the instructions from 1A to 1F.
    When adding the second cy43 program, it is automatically stored at the correct address.
    Now Python PIO knows that the program space is occupied.

    Drawback:
    ---------

    This needs one statemachine. But at least 2 statemachines from PIO 1 can be used.
    
    Parameters
    ----------
    smId    
        the id of the statemachine to be use for the cyw43 program
    
    Returns
    -------
    
    the statemachine object created

    """
    sm = rp2.StateMachine(smId, cyw32_program,set_base = 24, sideset_base =29, out_base = 24 )        
    return sm

def ResetStatemachines():
    for i in range(0,8):
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
            #print(f"available {i} = {av}")
            rp2.StateMachine(i).irq(None)
        except ValueError as e :
            pass
            #print(f"cannot remove irq for statemachine {i} {e}")
