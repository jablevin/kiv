import sys
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import matplotlib
import numpy as np
from scipy import stats
import pyvisa as visa
import time
import pint


class Keithley6487_IV(object):
    """
    This class is built to run IV measurments for the Keithley 6487 DMM
    Parameters:
        start:    The voltage to start IV sweep
                  No default
        stop:     The voltage to end IV sweep
                  No default
        stepsize: The size of the voltage steps to be used in the sweep.
                  Absolute value is taken of this value
                  Default=0.1
        delay:    Determines the amount of time voltage is held at each step before
                  a measurement is taken
                  Default=2
        repeat:   The number of times that the measurement is conducted; is used
                  for error analysis
                  Default=1
        sleep:    The amount of time between repeat measurements; allows voltage
                  to completely drain before restarting
                  default=30
        ID:       The local address of the Keithley 6487
                  Default='GPIB0::22::INSTR'
    """
    def __init__(self, start, stop, stepsize=0.1, delay=2, repeat=1, sleep=30, ID='GPIB0::22::INSTR'):
        self.start = start
        self.stop = stop
        self.stepsize = stepsize
        self.delay = delay
        self.repeat = 1
        self.sleep = sleep
        self.nsteps = int(abs((stop - start) / stepsize) + 1)

        self.connect_keithley(ID)
        self.timeout()
        self.program_sens()
        self.program_sour()
        self.program_form()
        self.program_trig()
        self.program_syst()


    def connect_keithley(self, ID):
        """ Starts Connection to Keithley Meter """
        rm = visa.ResourceManager()
        self.keithley = rm.open_resource(ID)
        self.keithley.write("*RST")


    def timeout(self):
        """ Sets timout so that longer measurements are not cut short """
        self.keithley.timeout = ((self.nsteps*self.delay)*self.repeat + self.sleep*(self.repeat-1)) * 1000 + 1000


    def program_sens(self):
        """ Setting parameters in SENSor SCPI commands """
        self.keithley.write(":SENS:FUNC 'CURR:DC' ")
        self.keithley.write(":SENS:CURR:RANG:AUTO ON")


    def program_sour(self):
        """ Setting parameters in SOURce SCPI commands """
        self.keithley.write(":SOUR:VOLT:SWE:STAR ", str(self.start))
        self.keithley.write(":SOUR:VOLT:SWE:STOP ", str(self.stop))
        self.keithley.write(":SOUR:VOLT:SWE:STEP ", str(self.stepsize))
        self.keithley.write(":SOUR:VOLT:SWE:DEL ", str(self.delay))


    def program_form(self):
        """ Setting parameters in FORMat SCPI commands """
        self.keithley.write(":FORM:DATA ASC")
        self.keithley.write(":FORM:ELEM READ,VSO")


    def program_trig(self):
        """ Setting parameters in TRIGger SCPI commands """
        self.keithley.write(":TRIG:SOUR IMM")
        self.keithley.write(":TRIG:COUN ", str(self.nsteps))


    def program_syst(self):
        """ Setting parameters in SYSTem SCPI commands """
        self.keithley.write("SYST:ZCH OFF")


    @property
    def runtime(self):
        """ Provides an estimated runtime of complete measurement cycle """
        return (self.nsteps*self.delay)*self.repeat + self.sleep*(self.repeat-1)


    def begin_runs(self):
        """
        Begins the measurement cycle and stores values
        vso: The voltage source list
        full_curr_list: List of all currents measured in order of measurements
                        across repeat cycles
        full_vso_list:  List of all vso that correctly correspond to the order
                        of the currents in full_curr_list
        err: Standard errors for each current that correspond to voltages from
             vso variable list
        avg_curr: The averaged current at each vso value in vso variable list

        Several of these parameters are only applicable for when repeat is greater
        than 1. Otherwise the vso and full_vso_list will be the same for example
        """
        self.yvalues = {}
        for i in range(self.repeat):
            if i != 0:
                time.sleep(self.sleep)
            self.keithley.write(":SOUR:VOLT:SWE:INIT")
            self.result = self.keithley.query(":READ?")
            self.yvalues[i] = np.array(self.keithley.query_ascii_values(":FETC?"))
        self.vso = np.array(self.yvalues[0][1::2])
        self.full_curr_list = (np.array([[self.yvalues[i][::2][j] for i in range(self.repeat)] for j in range(self.nsteps)]).flatten())
        self.full_vso_list = np.array([[j for i in range(self.repeat)] for j in self.vso]).flatten()
        ylist = np.split(self.full_curr_list, self.nsteps)
        self.err = np.std(ylist, axis=1)
        self.avg_curr = np.mean(ylist, axis=1)


    def calc_resistance(self):
        """ Calculates resistance (in ohms) from slope of linear fit to IV data """
        self.slope, self.intercept, self.r, self.p, self.std_error = stats.linregress(self.full_vso_list, self.full_curr_list)
        self.resistance = (1 / self.slope)


    def calc_resistivity(self, length=None, SA=None, U=None, units=None):
        """ Calculates resistivity based on input length and surface area (SA)
        of sample under measurement. Requires units from pint UnitRegistry
        U is the variable assigned from pint such as U=pint.UnitRegistry() and
        units is formatted such as units=U.Tohms*U.cm to achieve resistivity in
        units of Teraohms*cm. length and SA both require attached units """
        self.calc_resistance()
        if length and SA and U and units:
            self.resistivity = (self.resistance*U.ohms * SA / length).to(units)


    def plot(self, fit=False, save=None):
        """ Automatically plots the acquired data. Fit is set to true when
        a linear line should be fit to data and plotted. Save is the name of
        figure to be saved as, will not be saved unless provided.
        """
        legend = [Line2D([0], [0], marker='o', color='w', label='Datapoints',
                                  markerfacecolor='navy', markersize=15)]
        if fit:
            self.calc_resistance()
            legend.append(Line2D([0], [0], color='darkorange', lw=4, label='Fitted Linear Line'))
            legend.append(Line2D([0], [0], color='white', label='$R^2$: '+str(self.r**2)[:5]))
            legend.append(Line2D([0], [0], color='white', label='Resistance: '+str(self.resistance)+
                                  '$\; \Omega$'))

        matplotlib.rcParams.update({'font.size': 12})
        plt.figure(figsize=(12,8))
        if self.repeat > 1:
            plt.errorbar(self.vso, self.avg_curr, yerr=self.err, fmt='o', capsize=5, color='navy')
        else:
            plt.scatter(self.vso, self.avg_curr, color='navy')
        if fit:
            plt.plot(self.vso, self.slope*self.vso + self.intercept, color='darkorange')
        plt.xlabel('Voltage (V)')
        plt.ylabel('Current (A)')
        plt.title('IV Curve')
        plt.legend(handles=legend)
        plt.tight_layout()
        if save:
            plt.savefig(save)
        else:
            plt.show()

    def write_csv(self, filename):
        """ Writes data to CSV file """
        data = np.array((self.vso, self.full_curr_list))
        np.savetxt(filename, data, delimiter=',')


    def close_keithley(self):
        """ Call this function to close connection to Keithley 6487  """
        self.keithley.close()





class Keithley6517B_IV(object):
    """
    This class is built to run IV measurments for the Keithley 6487 DMM
    Parameters:
        start:    The voltage to start IV sweep
                  No default
        stop:     The voltage to end IV sweep
                  No default
        stepsize: The size of the voltage steps to be used in the sweep.
                  If incorrect sign is given, automatically corrected to match
                  start and stop value requirements
                  Default=0.1
        delay:    Determines the amount of time voltage is held at each step before
                  a measurement is taken
                  Default=2
        repeat:   The number of times that the measurement is conducted; is used
                  for error analysis
                  Default=1
        sleep:    The amount of time between repeat measurements; allows voltage
                  to completely drain before restarting
                  default=30
        ID:       The local address of the Keithley 6487
                  Default='GPIB0::22::INSTR'
    """
    def __init__(self, start, stop, stepsize=0.1, delay=2, repeat=1, sleep=30, ID='GPIB0::22::INSTR'):
        self.start = start
        self.stop = stop

        if start > stop and stepsize > 0:
            self.stepsize = -stepsize
        elif start > stop and stepsize < 0:
            self.stepsize = stepsize
        elif start < stop and stepsize > 0:
            self.stepsize = stepsize
        elif start < stop and stepsize < 0:
            self.stepsize = -stepsize

        self.delay = delay
        self.repeat = 1
        self.sleep = sleep
        self.nsteps = int(abs((stop - start) / stepsize) + 1)

        self.connect_keithley(ID)
        self.timeout()
        self.program_sens()
        self.program_tseq()
        self.program_form()
        self.program_trig()
        self.program_syst()


    def connect_keithley(self, ID):
        """ Starts Connection to Keithley Meter """
        rm = visa.ResourceManager()
        self.keithley = rm.open_resource(ID)
        self.keithley.write("*RST")


    def timeout(self):
        """ Sets timout so that longer measurements are not cut short """
        self.keithley.timeout = ((self.nsteps*self.delay)*self.repeat + self.sleep*(self.repeat-1)) * 1000 + 1000


    def program_sens(self):
        """ Setting parameters in SENSor SCPI commands """
        self.keithley.write(":SENS:FUNC 'CURR:DC' ")
        self.keithley.write(":SENS:CURR:RANG:AUTO ON")


    def program_tseq(self):
        """ Setting parameters in SOURce SCPI commands """
        self.keithley.write(":TSEQ:STSW:STAR ", str(self.start))
        self.keithley.write(":TSEQ:STSW:STOP ", str(self.stop))
        self.keithley.write(":TSEQ:STSW:STEP ", str(self.stepsize))
        self.keithley.write(":TSEQ:STSW:STIME ", str(self.delay))
        self.keithley.write(":TSEQ:TYPE STSW")
        self.keithley.write(":TSEQ:TSO BUS")


    def program_form(self):
        """ Setting parameters in FORMat SCPI commands """
        self.keithley.write(":FORM:DATA ASC")
        self.keithley.write(":FORM:ELEM READ,VSO")


    def program_trig(self):
        """ Setting parameters in TRIGger SCPI commands """
        self.keithley.write(":TRIG:COUN ", str(self.nsteps))


    def program_syst(self):
        """ Setting parameters in SYSTem SCPI commands """
        self.keithley.write("SYST:ZCH OFF")


    @property
    def runtime(self):
        """ Provides an estimated runtime of complete measurement cycle """
        return (self.nsteps*self.delay)*self.repeat + self.sleep*(self.repeat-1)


    def begin_runs(self):
        """
        Begins the measurement cycle and stores values
        vso: The voltage source list
        full_curr_list: List of all currents measured in order of measurements
                        across repeat cycles
        full_vso_list:  List of all vso that correctly correspond to the order
                        of the currents in full_curr_list
        err: Standard errors for each current that correspond to voltages from
             vso variable list
        avg_curr: The averaged current at each vso value in vso variable list

        Several of these parameters are only applicable for when repeat is greater
        than 1. Otherwise the vso and full_vso_list will be the same for example
        """
        self.yvalues = {}
        for i in range(self.repeat):
            if i != 0:
                time.sleep(self.sleep)
            self.keithley.write(":TSEQ:ARM")
            self.keithley.write("*TRG")
            time.sleep(int(self.runtime)+5)
            self.yvalues[i] = np.array(self.keithley.query_ascii_values(":TRACE:DATA?"))
        self.vso = np.array(self.yvalues[0][1::2])
        self.full_curr_list = (np.array([[self.yvalues[i][::2][j] for i in range(self.repeat)] for j in range(self.nsteps)]).flatten())
        self.full_vso_list = np.array([[j for i in range(self.repeat)] for j in self.vso]).flatten()
        ylist = np.split(self.full_curr_list, self.nsteps)
        self.err = np.std(ylist, axis=1)
        self.avg_curr = np.mean(ylist, axis=1)


    def calc_resistance(self):
        """ Calculates resistance (in ohms) from slope of linear fit to IV data """
        self.slope, self.intercept, self.r, self.p, self.std_error = stats.linregress(self.full_vso_list, self.full_curr_list)
        self.resistance = (1 / self.slope)


    def calc_resistivity(self, length=None, SA=None, U=None, units=None):
        """ Calculates resistivity based on input length and surface area (SA)
        of sample under measurement. Requires units from pint UnitRegistry
        U is the variable assigned from pint such as U=pint.UnitRegistry() and
        units is formatted such as units=U.Tohms*U.cm to achieve resistivity in
        units of Teraohms*cm. length and SA both require attached units """
        self.calc_resistance()
        if length and SA and U and units:
            self.resistivity = (self.resistance*U.ohms * SA / length).to(units)


    def plot(self, fit=False, save=None):
        """ Automatically plots the acquired data. Fit is set to true when
        a linear line should be fit to data and plotted. Save is the name of
        figure to be saved as, will not be saved unless provided.
        """
        legend = [Line2D([0], [0], marker='o', color='w', label='Datapoints',
                                  markerfacecolor='navy', markersize=15)]
        if fit:
            self.calc_resistance()
            legend.append(Line2D([0], [0], color='darkorange', lw=4, label='Fitted Linear Line'))
            legend.append(Line2D([0], [0], color='white', label='$R^2$: '+str(self.r**2)[:5]))
            legend.append(Line2D([0], [0], color='white', label='Resistance: '+str(self.resistance)+
                                  '$\; \Omega$'))

        matplotlib.rcParams.update({'font.size': 12})
        plt.figure(figsize=(12,8))
        if self.repeat > 1:
            plt.errorbar(self.vso, self.avg_curr, yerr=self.err, fmt='o', capsize=5, color='navy')
        else:
            plt.scatter(self.vso, self.avg_curr, color='navy')
        if fit:
            plt.plot(self.vso, self.slope*self.vso + self.intercept, color='darkorange')
        plt.xlabel('Voltage (V)')
        plt.ylabel('Current (A)')
        plt.title('IV Curve')
        plt.legend(handles=legend)
        plt.tight_layout()
        if save:
            plt.savefig(save)
        else:
            plt.show()


    def write_csv(self, filename):
        """ Writes data to CSV file """
        data = np.array((self.vso, self.full_curr_list))
        np.savetxt(filename, data, delimiter=',')


    def close_keithley(self):
        """ Call this function to close connection to Keithley 6487  """
        self.keithley.close()
