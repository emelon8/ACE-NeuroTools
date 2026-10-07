"""
ONIX analog-input visualizer.

Run as a script (not imported as a module):
    python scripts/import_agent_analyzer.py

All file I/O and plotting happens only when executed directly.
"""

import matplotlib.pyplot as plt
import numpy as np


def import_agent_analyzer(suffix: str = "2024-08-22T14_16_06") -> str:
    """Prompt user for file suffix and return it for data import.

    Args:
        suffix: Default file suffix if user provides no input.

    Returns:
        User-provided or default file suffix string.
    """
    user_input = input("Enter file suffix: ")
    if user_input:
        suffix = user_input
    print(f"Using suffix: {suffix}")
    return suffix


def plot_O2(analog_input: dict) -> None:
    """Plot oxygen percentage over time from analog input data."""
    plt.figure()
    plt.title("%O2 vs Time (s)")
    plt.plot(analog_input["time"], analog_input["O2"])
    plt.xlabel("time (sec)")
    plt.ylabel("% O2")
    plt.legend(["O2"])
    plt.show()


def plot_CO2(analog_input: dict) -> None:
    """Plot carbon dioxide percentage over time from analog input data."""
    plt.figure()
    plt.title("%CO2 vs Time (s)")
    plt.plot(analog_input["time"], analog_input["CO2"])
    plt.xlabel("time (sec)")
    plt.ylabel("% CO2")
    plt.legend(["CO2"])


def plot_anesthetic(analog_input: dict, anesthetic: str = "SEV") -> None:
    """Plot anesthetic concentration over time."""
    plt.figure()
    plt.title(f"{anesthetic}% vs Time (s)")
    plt.plot(analog_input["time"], analog_input[anesthetic])
    plt.xlabel("time (sec)")
    plt.ylabel(f"% {anesthetic}")
    plt.legend([anesthetic])


if __name__ == "__main__":
    suffix = import_agent_analyzer()

    # Metadata
    dt = {
        "names": ("time", "acq_clk_hz", "block_read_sz", "block_write_sz"),
        "formats": ("datetime64[us]", "u4", "u4", "u4"),
    }
    meta = np.genfromtxt("start-time_" + suffix + ".csv", delimiter=",", dtype=dt)
    print(f"Recording was started at {meta['time']} GMT")

    # Analog Inputs
    analog_input = {}
    analog_input["time"] = np.fromfile("analog-clock_" + suffix + ".raw", dtype=np.uint64) / meta["acq_clk_hz"]
    analog_input["O2"] = np.fromfile(f"O2_{suffix}.raw", dtype=np.float32) * 10
    analog_input["CO2"] = np.fromfile(f"CO2_{suffix}.raw", dtype=np.float32)
    analog_input["SEV"] = np.fromfile(f"SEV_{suffix}.raw", dtype=np.float32)
    analog_input["ISO"] = np.fromfile(f"ISO_{suffix}.raw", dtype=np.float32)

    plt.close("all")

    plot_O2(analog_input)
    plot_CO2(analog_input)
    plot_anesthetic(analog_input)

    # Hardware FIFO buffer use
    dt2 = {"names": ("clock", "bytes", "percent"), "formats": ("u8", "u4", "f8")}
    memory_use = np.genfromtxt("memory-use_" + suffix + ".csv", delimiter=",", dtype=dt2)

    plt.figure()
    plt.plot(memory_use["clock"] / meta["acq_clk_hz"], memory_use["percent"])
    plt.xlabel("time (sec)")
    plt.ylabel("FIFO used (%)")

    plt.show()
