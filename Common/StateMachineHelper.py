import rp2
from machine import mem32

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
    return ADR_PIO0_BASE if pioNo  == 0 else ADR_PIO1_BASE

def SMAddress(pioNo,smNo):
    adr = PioAddress(pioNo)+OFF_SM_START+(smNo*SIZE_SM)+SMx_ADDR
    return (adr,mem32[adr])

def ResetStatemachines():
    for i in range(0,8):
        av = AnyAvailable(i)
        print(f"available = {av}")
        try:
            print(f"statemachine : {i} {rp2.StateMachine(i).active()}")
            rp2.StateMachine(i).active(0)
        except ValueError as e:
            print(f"cannot stop statemachine {i}  {e}")
            pass

    rp2.PIO(0).remove_program() # reset all
    rp2.PIO(1).remove_program() # reset all
    rp2.PIO(0).irq(None)
    rp2.PIO(1).irq(None)
    for i in range(0,8):
        try:
            av = AnyAvailable(i)
            print(f"available {i} = {av}")
            rp2.StateMachine(i).irq(None)
        except ValueError as e :
            pass
            print(f"cannot remove irq for statemachine {i} {e}")

