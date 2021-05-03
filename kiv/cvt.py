import matplotlib.pyplot as plt
from matplotlib import cm
import matplotlib
import numpy as np
import pyvisa as visa
import time


class Keithley6487_CVT(object):
    """
    This class is built to run time dependent current analysis for the Keithley 6487
        nval:     The number of values of the measurement
        volts:    A list of voltages to cycle over for the measurement;
                  MUST BE A LIST
        nplc:     Dictates the number of power line cycles (nplc) to be integrated
                        which also determines how fast data is acquired
                  For 60 hz power line: 1 nplc / 60 s = 0.0166 s time between
                        measurements
                  For 50 hz power line: 1 nplc / 50 s = 0.02 s  time between
                        measurments
        delay:    Time that system voltage is turned off while switching been
                  voltages in volts list
                  Default: 2 s
        ID:       The local address of the Keithley 6487
                  Default='GPIB0::22::INSTR'
    """
    def __init__(self, nval, volts, nplc, delay=2, ID='GPIB0::22::INSTR'):
        self.nval = nval
        self.volts = np.array(volts)
        self.nplc = nplc
        self.delay = 2
        self.times = {}
        self.curr = {}


    def setup_run(self, v):
        """ Sends all appropriate commands to Keithley 6487 to set system
        up to begin the runs
        """
        rm = visa.ResourceManager()
        self.keithley = rm.open_resource('GPIB0::22::INSTR')
        self.keithley.write("*RST")
        self.keithley.timeout = 50000
        self.keithley.write(":SYST:ZCH OFF")
        self.keithley.write(":SENS:FUNC 'CURR:DC'")
        self.keithley.write(":SENS:CURR:RANG:AUTO ON")
        self.keithley.write(":SENS:CURR:NPLC ", str(self.nplc))
        self.keithley.write(":FORM:DATA ASC")
        self.keithley.write(":FORM:ELEM READ,TIME")
        self.keithley.write(":TRIG:SOUR IMM")
        self.keithley.write(":TRIG:COUN ", str(self.nval))
        self.keithley.write(":SOUR:VOLT ", str(v))


    def begin_runs(self):
        """ Call this function to begin the runs across the entire voltage range
        given by volts
        """
        for i in volts:
            self.setup_run(i)
            self.keithley.write(":SOUR:VOLT:STAT ON")
            result = keithley.query(":READ?")
            self.yvalues = np.array(keithley.query_ascii_values(":FETC?"))
            self.keithley.write(":SOUR:VOLT:STAT OFF")
            self.times[i] = np.array(self.yvalues[1::2]) - self.yvalues[1]
            self.curr[i] = np.array(self.yvalues[0::2])
            time.sleep(self.delay)


    def plot(self, normalize=True, save=False, size=10, colormap='viridis'):
        """ Plots the data either normalized or raw
        Normalized data is preferred if finding time to steady-state current
        for example when determining appropriate delay time in IV measurement
        """
        if normalize:
            self.normalized = {}
            for volt in self.volts
                if volts < 0:
                    self.normalized[volt] = -((self.curr[volt] - np.min(self.curr[volt]))/np.ptp(self.curr[volt])) + 1
                else:
                    self.normalized[volt] = (self.curr[volt] - np.min(self.curr[volt]))/np.ptp(self.curr[volt])

        clist = (volts - np.min(volts))/np.ptp(volts)
        cmap = cm.get_cmap(colormap)
        matplotlib.rcParams.update({'font.size': 14})
        plt.figure(figsize=(12,8))
        if normalize:
            index = 0
            for volt in self.volts:
                plt.plot(self.times[volt], self.normalized[volt], label=str(volt), marker='o', lw=0,
                        color=cmap(clist[index]), s=size)
                plt.ylabel('Normalized Current [A]')
                index += 1
        else:
            index = 0
            for volt in self.volts:
                plt.plot(self.times[volt], self.curr[volt], label=str(volt), marker='o', lw=0,
                        color=cmap(clist[index]), s=size)
                plt.ylabel('Current [A]')
                index += 1
        plt.xlabel('Time [s]')
        plt.legend()
        plt.tight_layout()
        if save:
            plt.savefig(save)
        else:
            plt.show()


    def write_csv(self, filename, volt):
        """ Writes data to a csv """
        np.savetxt(filename, np.transpose((self.times[volt], self.curr[volt]), delimiter=','))


    def close_keithley(self):
        """ Call this function to close connection to Keithley 6487  """
        self.keithley.close()
