import numpy as np
import matplotlib.pyplot as plt

def import_agent_analyzer(suffix="2024-08-22T14_16_06"):
    """Prompt user for file suffix and return it for data import.
    
    Args:
        suffix: Default file suffix if user provides no input.
        
    Returns:
        User-provided or default file suffix string.
    """
    user_input = input("Enter file suffix: ")
    if user_input:
        suffix = user_input
    print(f"Using suffix: {suffix}")  # based on user's input
    return suffix

suffix = import_agent_analyzer()



# Metadata
dt = {'names': ('time', 'acq_clk_hz', 'block_read_sz', 'block_write_sz'),
'formats': ('datetime64[us]', 'u4', 'u4', 'u4')}
meta = np.genfromtxt('start-time_' + suffix + '.csv', delimiter=',', dtype=dt)
print(f"Recording was started at {meta['time']} GMT")

# Analog Inputs
analog_input = {}
analog_input['time'] = np.fromfile('analog-clock_' + suffix + '.raw', dtype=np.uint64) / meta['acq_clk_hz']
analog_input['O2'] = np.fromfile(f'O2_{suffix}.raw', dtype=np.float32) * 10  #multiply by 10 for O2
analog_input['CO2'] = np.fromfile(f'CO2_{suffix}.raw', dtype=np.float32)
analog_input['SEV'] = np.fromfile(f'SEV_{suffix}.raw', dtype=np.float32)
analog_input['ISO'] = np.fromfile(f'ISO_{suffix}.raw', dtype=np.float32)

plt.close('all')

def plot_O2():
    """Plot oxygen percentage over time from analog input data."""
    plt.figure()
    plt.title("%O2 vs Time (s)")
    plt.plot(analog_input['time'], analog_input['O2'])
    plt.xlabel("time (sec)")
    plt.ylabel("% O2") #goes 0-100% 1 volt = 10% O2
    plt.legend(['O2'])
    plt.show()
plot_O2()


def plot_CO2():
    """Plot carbon dioxide percentage over time from analog input data."""
    plt.figure()
    plt.title("%CO2 vs Time (s)")
    plt.plot(analog_input['time'], analog_input['CO2'])
    plt.xlabel("time (sec)")
    plt.ylabel("% CO2") #goes 0-10% based on volts 1 volt = 1%
    plt.legend(['CO2'])
plot_CO2()

def plot_anesthetic():
    """Plot anesthetic concentration over time.
    
    Uses sevoflurane (SEV) by default but can be modified for other agents.
    """
    plt.figure()
    anesthetic = "SEV" #Can change this to whatever one
    plt.title(f"{anesthetic}% vs Time (s)")
    plt.plot(analog_input['time'], analog_input[f'{anesthetic}'])
    plt.xlabel("time (sec)")
    plt.ylabel(f"% {anesthetic}" ) # goes 0-10% based on volts 1 volt = 1%
    plt.legend([f"{anesthetic}"])
plot_anesthetic()

# Hardware FIFO buffer use
dt = {'names': ('clock', 'bytes', 'percent'),
      'formats': ('u8', 'u4', 'f8')}
memory_use = np.genfromtxt('memory-use_' + suffix + '.csv', delimiter=',', dtype=dt)

plt.figure()
plt.plot(memory_use['clock'] / meta['acq_clk_hz'], memory_use['percent'])
plt.xlabel("time (sec)")
plt.ylabel("FIFO used (%)")

plt.show()