# -*- coding: utf-8 -*-
"""
Created on Tue Dec 19 14:18:48 2023

@author: ericm
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import miniscope_ephys

lineNum = 107
channel = 'PFCLFPvsCBEEG'
videoNum = 260 #{64: [60, 90], 107:[0, 37, 260]}

obj = miniscope_ephys.miniscopeEphys(lineNum=lineNum)
obj.importCaMovies(str(videoNum) + '.avi')
obj.findEphysIdxOfTTLEvents()

vmin = np.mean(obj.movie) - np.std(obj.movie)*0
vmax = np.mean(obj.movie) + np.std(obj.movie)*4

# Set up the plot
fig, ax = plt.subplots(figsize=(5.4,5.4))
plt.subplots_adjust(0,0,1,1)

# Define the update function
def update(frame):
    # Clear the plot
    ax.clear()

    # Plot the frame
    ax.imshow(obj.movie[frame], vmin=vmin, vmax=vmax, cmap='gray')

    # Get the corresponding segment of the ephys recording
    frame += videoNum * 1000
    if frame > 0:
        ephys_segment = obj.ephys[channel][obj.ephysIdxAllTTLEvents[frame-10]:obj.ephysIdxAllTTLEvents[frame]]
    else:
        ephys_segment = obj.ephys[channel][obj.ephysIdxAllTTLEvents[frame]-round(obj.samplingRate[channel]/obj.experiment['fr']):obj.ephysIdxAllTTLEvents[frame]]
    ephys_segment = -np.flip(ephys_segment) # flip and invert signal so it is flipped and inverted again when the movie is written.

    # Plot the segment on top of the frame
    ax.plot(np.linspace(-0.5, 607.5, len(ephys_segment)), ephys_segment/5 + 100, color='red', linewidth=2)
    # ax.set_xlim(0, len(ephys_segment))
    # ax.set_ylim(np.min(obj.ephys[channel]), np.max(obj.ephys[channel]))
    ax.set_xlim(-0.5, 607.5)
    ax.set_ylim(-0.5, 607.5)
    ax.set_axis_off()

# Create the animation
ani = animation.FuncAnimation(fig, update, frames=len(obj.movie), interval=33, repeat=False)

# Display the animation
plt.show()

# Save the animation
# ani.save(obj.experiment['calcium imaging directory'] + '/Miniscope/' + str(videoNum) + '_CaIm_and_' + channel + '.mp4', dpi=300)