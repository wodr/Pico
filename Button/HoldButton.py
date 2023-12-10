from machine import Pin
import rp2


@rp2.asm_pio(set_init=rp2.PIO.IN_HIGH)
def touchDetect():
    wrap_target()
    wait(0, pin, 0)    
    
    set(y,1)                # publish state pushed
    in_(y,32)   
    push(y)    
    irq(rel(0))
    
    set(x,31)               # modifiy x to change the hold detection duration
    label('loop')

    in_(pins,1)
    mov(y,isr)
    jmp(y_dec,'released')      
    jmp(x_dec,'loop') [31]  # modifiy delay to change the hold detection duration
    
    set(y,2)                # publish state hold
    in_(y,32)
    push(y)    
    irq(rel(0))

    set(x,0)                # set hold interrupt frequency
    jmp('loop')             # if hold irq should be continued. comment if only one hold interrupt needed
    label('released')
    wait(1, pin, 0)

    set(y,4)                # publish state released
    in_(y,32)
    push(y)
    irq(rel(0))

    wrap()


class HoldButton: 
    stateMachineIndex = 0
    Pressed = const(1)
    Hold = const(2)
    Released = const(4)
    
    def __init__(self, pin : int | Pin, callback = None):
        self.callback = callback
        self.eventCounter = 0 
        self.touchDetectRef = self.TouchDetect
        
        if( type(pin) is int):
            self.pin = Pin(pin,Pin.IN,Pin.PULL_UP)           
        elif( type(pin) is Pin):
            self.pin = pin
        else:
            raise ValueError(f"pin must be of type int or Pin : {type(pin)}")
        
        if( HoldButton.stateMachineIndex > 7):
            raise ValueError(f"only 8 buttons are supported because of 8 statemachines.")
        
       
            
        self.sm = rp2.StateMachine(HoldButton.stateMachineIndex,touchDetect,in_base=self.pin, freq=2000)        
        
        self.sm.active(1)        
        self.sm.irq(self.touchDetectRef,trigger=1, hard=False)
        print(f"active sm={HoldButton.stateMachineIndex} {self.sm}")                
        HoldButton.stateMachineIndex +=1
        
    def TouchDetect(self,sm):
        
        if( self.sm.rx_fifo()== 0 ):
            print(f"no msg {self.sm} {sm}")
            return
        
        buttonState = self.sm.get()
       
        self.eventCounter += 1
        
        if( self.callback != None):
            self.callback(self,buttonState)
            return
                
    def Stop(self):
        self.sm.active(0)
        self.sm.irq(None)
    
    def Reset(firstStateMachine):
        HoldButton.stateMachineIndex = firstStateMachine
        for i in range(0,2):            
            rp2.PIO(i).remove_program()                      
            rp2.PIO(i).irq(None)                          
        for i in range(0,8):
            try:
                rp2.StateMachine(i).active(0)
                rp2.StateMachine(i).irq(None)
            except ValueError:
                # todo fix 'StateMachine claimed by external resource'
                pass


            

if __name__ == '__main__':
    import time
    HoldButton.Reset(2)
    led = Pin("LED",Pin.OUT)
    

    def ButtonEvent(button, buttonState):
        global start
        f = "unknown"
        if( buttonState == HoldButton.Pressed):
            start = time.ticks_ms()
            led(1)
            f = "pressed"            
        elif( buttonState == HoldButton.Hold):
            led.toggle()
            f = "hold"
        elif( buttonState == HoldButton.Released):
            led(0)
            f = "released"
   
        print(f"{time.ticks_ms()-start:<8} {button.eventCounter:<3} {f:<10} {buttonState}")
        
# press the button, led is on 
# hold button, led flickers
# release button led is off.
# Nice side effect: There seems to be no bouncing if switched.

    button1 = HoldButton(22,ButtonEvent)
    time.sleep(3600)        
