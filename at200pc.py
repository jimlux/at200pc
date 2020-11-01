#! /usr/bin/env /usr/bin/python3
# for Windows change above to: hashbang python3

# Copyright (C) 2008-2010 by James C. Ahlstrom, N2ADR.
# Copyright (C) 2019 by Christopher Sylvain, KB3CS.
# This free software is licensed for use under the GNU General Public
# License (GPL), see http://www.opensource.org.
# Note that there is NO WARRANTY AT ALL.  USE AT YOUR OWN RISK!!

# modified by jimlux, 24 Oct 2020
# split AT200 interface from GUI



# Thanks to Chris, KB3CS, for additional code and features.
#
# adjusted SWR Threshold radiobuttons implementation            KB3CS 02/20/2010
# refactored for Python3.7  	                                KB3CS 09/04/2019
#   dependencies: pyserial
#   Win10 dependencies: pywin32 (formerly win32all)

# This controls the AT-200PC from LDG Electronics.  The buttons are:
#  Ant 1/2				Change antenna
#  Active/Passive		Passive: Zero added L and C, turn off AutoTune (pass thru)
#  Auto On/Off			Turn AutoTune on and off (auto start tune for high SWR)
#  Mem Tune				Tune from memory
#  L, C +/-				Add / Subtract one from inductance L or capacitance C
#  Z					Change direction of L-network
#  Store				Manually store L/C/Z for last frequency
#  Full Tune			Start a full tuning search
#  1.1, 1.3, 1.5, 1.7, 2.0, 2.5, 3.0
#                       Set / Show SWR autotuning threshold
# Please see the documentation for the AT-200PC or AT-200 Pro to understand this tuner.
""" constants from the LDG document """
PREAMBLE_BYTE = 165



import sys, time, math, traceback

DEBUG = False

# This is the serial port name.  You probably need to change it:
if sys.platform[0:3] == "win":
  TTY_NAME = "COM4"   # Windows name of serial port for the AT-200PC
else:
  TTY_NAME = "/dev/ttyUSB0" # Linux name of serial port for the AT-200PC
if sys.platform[0:3] == "win":
  try:
    import win32file    # This is part of the win32all module by Mark Hammond
  except:
    win32file = None
else:
  win32file = 1       # win32file not needed on Linux

try:
  import serial     # This is pySerial; it provides serial port support.
except:
  serial = None

""" tunercontrol - this is the low level inteface to the physical hardware"""
class tunercontrol:
    def __init__(self,name,port):
        self.name = name
        self.serial=None
        self.rx_state = 0

        try:
            self.serial = serial.Serial(
                port = port,
                #baudrate = 19200,
                #parity = serial.PARITY_NONE,
                #stopbits = serial.STOPBITS_ONE,
                #bytesize = serial.EIGHTBITS,
                timeout = 1.0,
                writeTimeout = 0
                )
            self.serial.setRTS(0)

        except serial.SerialException:
            print("Serial port not found: %s"%port)
        else:
            pass
    """ debug routine copied from old code """
    def Write(self,s):
        if DEBUG:
          print('Write', ord(s[0]))
        if self.serial:
          try:
            
            self.serial.setRTS(1)   # Wake up the AT-200PC
            time.sleep(0.003)       # Wait 3 milliseconds
            self.serial.write(s.encode())
            self.serial.setRTS(0)
            time.sleep(0.010)       # Wait
          
          except:
            traceback.print_exc()

    def SendCmd(self,cmd,byte2=0,byte3=0):
      """ commands are sent to the AT200PC by asserting RTS for a time, then sending 4 bytes"""
      """ TODO probably should add some code to check CTS, which is deasserted when the tuner is busy"""
      s = bytearray([PREAMBLE_BYTE,cmd,byte2,byte3])
      if DEBUG:
        print('Send', s)
      if self.serial:
        try:
          self.serial.setRTS(1) # Wake up the AT-200PC
          time.sleep(0.003)   # Wait 3 milliseconds
          self.serial.write(s)
          self.serial.setRTS(0)
          time.sleep(0.010)   # Wait
        except:
          traceback.print_exc()     
        
    def RecvReq(self):
        byte1=0
        byte2 = 0
        byte3 = 0
        blocksrcv = []
        if self.serial:
            try:
              chars = self.serial.read(1024)  # This will always time out
            except:
              chars = ''
              traceback.print_exc()
        else:
            print ("serial not up")
            chars = ''
        if DEBUG:
            print("chars received:",len(chars),chars)
        for ch in chars:
            if DEBUG:
                print('recv:',ch)
            if self.rx_state == 0:  # Read first of 4 characters; must be decimal 165
              if ch == 165:
                self.rx_state = 1
            elif self.rx_state == 1:  # Read second byte
              self.rx_state = 2
              self.rx_byte1 = ch
            elif self.rx_state == 2:  # Read third byte
              self.rx_state = 3
              self.rx_byte2 = ch
            elif self.rx_state == 3:  # Read fourth byte
              self.rx_state = 0
              byte3 = ch
              byte1 = self.rx_byte1
              byte2 = self.rx_byte2
              blocksrcv.append([byte1,byte2,byte3])
              if DEBUG:
                print('Received', byte1, byte2, byte3)
        return blocksrcv

""" tuner is the class that defines higher level interface to the tuner"""

REQ_NOOP = 0
REQ_INDUP = 1
REQ_INDDN = 2
REQ_CAPUP = 3
REQ_CAPDN = 4
REQ_MEMTUNE = 5
REQ_FULLTUNE = 6
REQ_HIZ = 8
REQ_LOZ = 9
REQ_ANT1 = 10
REQ_ANT2 = 11

REQ_ALLUPDATE = 40
REQ_VERSION = 41
REQ_ARM_CLEAR = 42
REQ_CLEAR_MEM = 43
REQ_TUNER_STANDBY = 44
REQ_TUNER_ACTIVE = 45
REQ_MANUAL_STORE = 46       # store current L & C at table corresponding to last freq read
REQ_SWR11 = 50              # tune thresholds
REQ_SWR13 = 51
REQ_SWR15 = 52
REQ_SWR17 = 53
REQ_SWR20 = 54
REQ_SWR25 = 55
REQ_SWR30 = 56
REQ_RESET = 57              # reset all the relays to zero
REQ_AUTO_ON = 58
REQ_AUTO_OFF = 59
REQ_FWD_PWR = 60            # get fwd pwr measurement
REQ_REV_PWR = 61            # get rev pwr measurement
REQ_SWR = 62                # get Current SWR
REQ_UPDATE_ON = 63
REQ_UPDATE_OFF = 64
REQ_SET_IND = 65
REQ_SET_CAP = 66
REQ_SET_FREQ = 67
REQ_MEM_DUMP = 68


CMD_NOOP = 0
CMD_INDVAL = 1
CMD_CAPVAL = 2
CMD_HILOZ = 3
CMD_ANTENNA = 4           # byte 2 is either 1 or 2

CMD_FWDPWR = 5
CMD_REVPWR = 18
CMD_SWR = 6
CMD_TXFREQ =7
CMD_TUNEPASS = 9
CMD_TUNEFAIL = 10
CMD_VERSION = 11
CMD_CLEAR_DONE = 12
CMD_INSTANDBY = 13
CMD_ACTIVE = 14
CMD_STORE_OK = 15
CMD_SWRTHRESH = 16

SWR_ReturnValues = [1.1,1.3,1.5,1.7,2.0,2.5,3.0]

CMD_AUTO_STATUS = 17
CMD_UPDATE_STATUS = 19

CMD_VAL_DISABLE = 0
CMD_VAL_ENABLE = 1

class tuner:
    def __init__(self,tunerinterface):
        self.tif = tunerinterface

    def SetInd(self,indidx=0):
      self.tif.SendCmd(REQ_SET_IND,indidx,0)

    def SetCap(self,capidx=0):
      self.tif.SendCmd(REQ_SET_CAP,indidx,0)
      
    def SetHi(self):
      pass
    def SetLo(self):
      pass
    def GetFwd(self):
      return 0
    def GetRev(self):
      return 0
    def GetSWR(self):
      return 0
    def GetVersion(self):
      return 0

    def StatusDecode(self,blocks):
        for block in blocks:
            b1 = block[0]
            b2 = block[1]
            b3 = block[2]
            if b1 == CMD_INDVAL:
                print("inductor value:",b2)
            elif b1 == CMD_CAPVAL:
                print("capacitor value:",b2)
            elif b1 == CMD_HILOZ:
                print("High Low:",b2)
            elif b1 == CMD_ANTENNA:
                print("Antenna:",b2)
            elif b1 == CMD_VERSION:
                print("Version",b2,b3)
            elif b1 == CMD_FWDPWR:
                pwrf = float(b2*256 + b3)/100.
                print("Forward Power:",pwrf)
            elif b1 == CMD_REVPWR:
                pwrr = float(b2*256 + b3)/100.
                print("Reverse Power:",pwrr)
            elif b1 == CMD_SWR:
                rho2 = float(b3)/256.
                rho = math.sqrt(rho2)
                swr = (1+rho)/(1-rho)
                print("Rho, SWR:",rho,swr)
            elif b1 == CMD_TXFREQ:
                ticks = float(b2*256+b3)
                if ticks == 0:
                    freq = 0
                else:
                    freq = 20480.0 / ticks
                print("Freq, MHz:",freq)
            elif b1 == CMD_TUNEPASS:
                print ("Tune ok")
            elif b1 == CMD_TUNEFAIL:
                if b2 ==0:
                    failreason = "no RF"
                elif b2 == 1:
                    failreason = "Carrier lost before complete"
                elif b2 == 2:
                    failreason = "Couldn't get SWR low enough"
                else:
                    failreason = "unknown"
                print("Tune failed:"+faireason)
            elif b1 == CMD_CLEAR_DONE:
                print ("EEPROM clear complete")
            elif  b1 == CMD_INSTANDBY:
                print ("Tuner in standby")
            elif b1 == CMD_ACTIVE:
                print ("Tuner Active")
            elif b1 == CMD_STORE_OK:
                print ("Manual Memory Store Complete")
            elif b1 == CMD_SWRTHRESH:
                print ("SWR Threshold",b2,SWR_ReturnValues[b2])
            elif b1 == CMD_AUTO_STATUS:
                print ("Auto Tune:" + ("On" if b2==1 else "Off"))
            elif b1 == CMD_UPDATE_STATUS:
                print ("Live Uptates:"+("On" if b2==1 else "Off"))


            else:
                print("unrecognized",b1,b2,b3)

""" tunerformat is methods that make human readable output"""

class tunerformat:
    def FwdPower(self,dn=0):
        pass


# These are other AT-200PC parameters you can set:
REQ_LIVEUPDATE = 63			# Send power and swr when RF is present: ON=63, OFF=64





def About(): # for those not inclined to RTFC (c == code) :-)
      s = 'LDG AT-200PC Control Script\n'
#      s = s + 'Copyright (C) 2008-2010 by James C. Ahlstrom, N2ADR. All rights reserved.\n\n'
      s = '\nCopyright (C) 2008-2010 by James C. Ahlstrom, N2ADR. All rights reserved.\n'
      s = s + 'Copyright (C) 2019 by Christopher Sylvain, KB3CS. All rights reserved.\n'
      s = s + 'Copyright (C) 2020 by James Lux, W6RMK. All rights reserved.\n'
      s = s + 'This free software is licensed for use under the GNU General Public License (GPL),\n'
      s = s + 'see http://opensource.org/licenses/alphabetical \n'
      s = s + 'Note that there is NO WARRANTY AT ALL. USE AT YOUR OWN RISK!!\n'

      print(s)

if __name__ == "__main__":

    About()
    tif = tunercontrol("tuner 1",port=TTY_NAME)
    if not tif:
      if not win32file:
        print("Missing Python module win32all")
      elif not serial:
        print("Missing Python module pySerial")
      else:
        print("Can not open serial port %s" % TTY_NAME)

    print ("set antenna 1")
    t = tuner(tif)
    tif.Write(chr(10))
    a= tif.RecvReq()
    print ("received:",a)
    print ("status:",t.StatusDecode(a))
    

    tif.Write(chr(11))

    a= tif.RecvReq()
    print ("received:",a)
    print ("status:",t.StatusDecode(a))

    time.sleep(1.0)
    print("version")

    tif.SendCmd(REQ_VERSION)
    a= tif.RecvReq()
    print ("received:",a)
    print ("status:",t.StatusDecode(a))

    time.sleep(1.0)
    print("all status")
    tif.SendCmd(REQ_ALLUPDATE)
    a= tif.RecvReq()
    print ("received:",a)
    print ("status:",t.StatusDecode(a))


    """ not sure we need this 
    if serial:
      serial.close()
      serial = None
    """
    running = 0
