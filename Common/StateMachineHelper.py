import rp2
from machine import mem32
StateMachineFrequency  =  const(125_000_000)

def ResetStatemachines():
    for i in range(0,8):
        if i == 4 :
            continue
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
