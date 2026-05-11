import csv
import os
from typing import cast

import matplotlib.pyplot as plt

from aceneurotools.shared.misc_functions import conv_quat_to_euler


# two functions for computing/plotting rat head direction data
def quat_file_to_euler(filename: str = 'head_orientation.csv', nf: str = 'True'):
    """Convert quaternion orientation data to Euler angles.
    
    Reads a CSV file containing quaternion data and converts each row
    to Euler angles (x, y, z rotations).
    
    Args:
        filename: Path to input CSV with quaternion data.
        nf: If 'True', write results to new file; otherwise return matrix.
        
    Returns:
        If nf='True': Path to new CSV file with Euler angles.
        Otherwise: Matrix of Euler angle values.
    """
    new_filename = filename.replace('.csv', 'in_euler_angles.csv')
    if os.path.exists(filename):
        print('File exists')
        with open(filename, newline='') as f:
            reader = csv.reader(f)
            if nf == 'True':  # do you want to create a new file
                with open(new_filename, 'w', newline='') as outfile:
                    writer = csv.writer(outfile)
                    header = ['Time Stamp (ms)', 'x', 'y', 'z']
                    writer.writerow(header)
                    next(f)
                    for line in reader:
                        euler_angles = conv_quat_to_euler(line)
                        if euler_angles:
                            writer.writerow(euler_angles)
                return new_filename
            else:
                matrix = []
                next(f)
                for line in reader:
                    euler_angles = conv_quat_to_euler(line)
                    if euler_angles:
                        matrix.append(euler_angles)
                return matrix


def graph_movement(filename: str = 'head_orientation_in_euler_angles.csv', plot_name: str = 'movement_plot.png'):
    """Plot angular velocity over time from Euler angle data.
    
    Computes the rate of change of head orientation and plots it over time.
    
    Args:
        filename: Path to CSV file with Euler angles or quaternions.
        plot_name: Output filename for the saved plot.
    """
    if 'in_euler_angles.csv' not in filename and '.csv' in filename:
        filename = cast(str, quat_file_to_euler(filename))
    elif '.csv' not in filename:
        print('!!! ERROR: Invalid file')
        return

    if os.path.exists(filename):
        print('File exists')
        with open(filename, newline='') as f:
            reader = csv.reader(f)
            y = []
            avg_angle = []
            time = []
            next(f)  # skip header line
            for line in reader:
                if len(line) != 4:
                    print('!!! ERROR: Invalid file') #FIXME
                    return
                euler_anglesum = (float(line[1]) + float(line[2]) + float(
                    line[3])) / 3  # FIXME change to difference between angles instead of averaging the angles
                avg_angle.append(euler_anglesum)
                time.append(float(line[0]))
            count = 1  # skips first line
            while count < len(avg_angle):
                delta_angle = abs((avg_angle[count]) - avg_angle[count - 1])
                delta_time = abs(time[count] - avg_angle[count - 1])
                y.append(delta_angle / delta_time)
                count += 1
            # TODO: Take diff between rows for 3 columns, combine to single value
            x = list(time[1:])  # skips first time
            y = list(y)
            plt.plot(x, y)
            plt.xlabel('time(ms)')
            plt.ylabel('angle change over time (rad/s)')
            plt.title('movement over time')
            plt.show()
            plt.savefig(plot_name)
    else:
        print('!!! ERROR: File not found') #FIXME
        return
