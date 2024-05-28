from machine import Pin
import rp2

#  Input 0 - 5v
#  settle for 50% step 2.5V : 300 ms !!
#  settle for 10% step 0.5V : 250 ms !!
#  settle for 2% step 0.1V :  200 ms !!
#  R1 = 82k, C1 = 220nF C2 = C3 = 150nF
#  Measure Values
#  ==============
#  Frequency  Amplitue   dB
#   Hz          V   
#   5	        3.8	   -2.38
#   5,6	        3.52   -3.04
#   10	        1.92   -8.31
#   20	        0.55   -19.1
#   30	        0.22   -27.13
#   40	        0.11   -33.15
#   50	        0.07   -37.07
#   60	        0.05   -40
#   70	        0.04   -41.93
#   80	        0.03   -44.43
#   90	        0.02   -47.95
#
# Calculated Values
# http://sim.okawa-denshi.jp/en/Sallen3tool.php
# =================
# -  3 dB at      4.35 Hz
# - 40 dB at ~   50 Hz
# - 50 dB at ~  100 Hz
# -120 dB at ~ 1000 Hz     => 5uV resolution (for 5 Vpp input)
# 

@rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW)
def pwm_program():
    pull(noblock) .side(0)
    mov(x, osr)                 # Keep most recent pull data stashed in X, for recycling by noblock
    mov(y, isr)                 # ISR must be preloaded with PWM count max    
    label("pwmloop")
    jmp(x_not_y, "skip")
    nop()         .side(1)
    label("skip")
    jmp(y_dec, "pwmloop")

## https://docs.micropython.org/en/latest/library/rp2.PIO.html

class PwmHighResolution:
    _InstructionsPerLoop = const(2)
    _StateMachineFrequency = const(125_000_000)
    # Limit duty so, that max voltage is not exceeded
    Uupper = 5
    Umax = 4.096
    #Umax = 5
    def __init__(self, pwmPin, frequency=None,maxCount=None,stateMachineIndex=4,invertDuty=False):
        # duty = 0 => 0V 
        # duty = 100 => Umax
        self.invertDuty = invertDuty
        self.duty = 0 
        self.maxCount = 0 
        self.outputMaxCount =  0     # scale to 0.. Umax
        self.frequency = 0
        self.pwmPin = Pin(pwmPin)
        self.smPwm = rp2.StateMachine(stateMachineIndex, pwm_program, sideset_base=self.pwmPin)
        if( maxCount is not None):
            self.setMaxCount(maxCount)
        elif( frequency is not None):
            self.setFrequency(frequency)        
        else:
            self.setFrequency(10)        
        
    
    def setMaxCount(self,maxCount):
        self.smPwm.active(0)        
        d = self.getDuty()  # save old duty
        self.maxCount = maxCount
        self.frequency = _StateMachineFrequency / (self.maxCount * _InstructionsPerLoop)                            
        print(f" frequency={self.frequency} Hz {self.smPwm}  granularity={self.maxCount}")        
        self.smPwm.put(self.maxCount)
        self.smPwm.exec("pull()")
        self.smPwm.exec("mov(isr, osr)")                
        self.setDuty(d) # restore duty
        self.smPwm.active(1)
        self.outputMaxCount = int(self.maxCount *  PwmHighResolution.Umax / PwmHighResolution.Uupper)
        return self.maxCount

    def setFrequency(self,frequency):
        # frequency might not match exactly
        
        self.smPwm.active(0)           
        d = self.getDuty()  # save old duty
        self.maxCount = int(_StateMachineFrequency / ( _InstructionsPerLoop * frequency))
        self.frequency = _StateMachineFrequency / (self.maxCount * _InstructionsPerLoop)                            
        print(f" frequency={frequency} Hz statemachine  granularity={self.maxCount}")        
        self.smPwm.put(self.maxCount)
        self.smPwm.exec("pull()")
        self.smPwm.exec("mov(isr, osr)")                
        self.setDuty(d) # restore duty
        self.smPwm.active(1)
        self.outputMaxCount = int(self.maxCount *  PwmHighResolution.Umax / PwmHighResolution.Uupper)
        print(f"maxCount = {self.maxCount} {self.outputMaxCount}")
        
        return self.frequency

    def setDutyRaw(self,valueRaw):

        valueRaw = max(valueRaw, -1)
        valueRaw = min(valueRaw, self.maxCount)
        
        if( valueRaw > self.outputMaxCount):
            valueRaw = self.outputMaxCount

        # depending on high / low translation for photo coupler    
        valueRaw = self.maxCount - valueRaw  if self.invertDuty  else  valueRaw
        
        self.duty  = int(valueRaw)

        #print(f"dutyRaw = {self.duty} valueRaw={valueRaw} max={self.maxCount} %={self.duty/self.maxCount}")
        self.smPwm.put(self.duty) 
        return self.getDutyRaw()
            
    def getDutyRaw(self):        
        return self.duty
    
    def setDuty(self, value):    
        """ 
        value is 0.0 to 100.0
        """                    
        valueRaw = int((self.maxCount * value // 100))
        print(f"{valueRaw}")
        self.setDutyRaw(valueRaw)
        return self.getDuty()
    
    def getDuty(self):     
        if( self.maxCount == 0 ):
            return 50
        return self.duty / self.maxCount * 100 
    
    def setT(self, durationHigh):
        """
        duration in seconds, should be in the range of 0 and 1/f
        """
        raw = (durationHigh * self.frequency * self.maxCount)        
        self.setDutyRaw(raw)
        return self.getT()

    def getT(self):
        """ get duty as time in seconds
        """
        return (self.duty  / self.maxCount)  / self.frequency

#print(__name__)
c = None
if __name__ == '__main__':
    import time
    import math
    pwm = None
    Umax = 5
    Umeasure = 4.096
    
    pwm = PwmHighResolution(16,maxCount=50000,stateMachineIndex=7)         
    frequency = pwm.frequency

    def MeasureSettle():
        while(True):
            pwm.setDuty(5)
            time.sleep(1)
            pwm.setDuty(95)
            time.sleep(1)

    def TestPwmHighResolution():
   
        print(f"Umax = {Umax} resolution = {pwm.maxCount} frequency={pwm.frequency:.2f} Hz step = {1/pwm.maxCount*100}  min step {Umax/pwm.maxCount*1e6} % uV bits = {math.log2(pwm.maxCount):.1f} fsr {math.log2(pwm.maxCount/Umax*Umeasure)} {Umeasure}")
        # 42597,45874
        #pwm.setDutyRaw(45874)1+2
        #time.sleep(100)
        # periode : 200 ms
        for i in range (1,5):        
            t = i/20 *1/frequency
            pwm.setT(t)    
            print(f"{t} {pwm.getT()} {pwm.getDuty()} {pwm.getDutyRaw()}")
            time.sleep(0.5)

        pwm.setDuty(50)

    pwm.setDuty(50)
    MeasureSettle()
    