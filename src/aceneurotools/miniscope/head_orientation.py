"""Head-orientation conversions for Miniscope V4 BNO055 IMU data.

The V4 miniscope logs head orientation as quaternions in ``headOrientation.csv``;
these helpers convert them to Euler angles (roll, pitch, yaw).
"""

import math
from typing import Any

import numpy as np


def quat_to_euler(qw: float, qx: float, qy: float, qz: float, degrees: bool = False) -> list[float]:
    """Convert quaternion to Euler angles (roll, pitch, yaw).
    
    Args:
        qw: Quaternion w component.
        qx: Quaternion x component.
        qy: Quaternion y component.
        qz: Quaternion z component.
        degrees: If True, return angles in degrees; otherwise radians.
        
    Returns:
        List of [roll, pitch, yaw] angles.
    """
    m00 = 1.0 - 2.0 * qy * qy - 2.0 * qz * qz
    m01 = 2.0 * qx * qy + 2.0 * qz * qw
    m02 = 2.0 * qx * qz - 2.0 * qy * qw
    m10 = 2.0 * qx * qy - 2.0 * qz * qw
    m11 = 1 - 2.0 * qx * qx - 2.0 * qz * qz
    m12 = 2.0 * qy * qz + 2.0 * qx * qw
    m20 = 2.0 * qx * qz + 2.0 * qy * qw
    m21 = 2.0 * qy * qz - 2.0 * qx * qw
    m22 = 1.0 - 2.0 * qx * qx - 2.0 * qy * qy

    eulerAngles = []

    R = np.arctan2(m12, m22)  # Roll
    eulerAngles.append(R)
    c2 = np.sqrt(m00 * m00 + m01 * m01)
    P = np.arctan2(-m02, c2)  # Pitch
    eulerAngles.append(P)
    s1 = np.sin(R)
    c1 = np.cos(R)
    Y = np.arctan2(s1 * m20 - c1 * m10, c1 * m11 - s1 * m21)  # Yaw
    eulerAngles.append(Y)
    if degrees == True:
        eulerAngles = [math.degrees(R), math.degrees(P), math.degrees(Y)]
    return eulerAngles


def conv_quat_to_euler(line: list[Any]) -> list[Any] | None:
    """Convert a CSV line of quaternion data to Euler angles.
    
    Args:
        line: List of [time, qw, qx, qy, qz].
        
    Returns:
        List of [time, roll, pitch, yaw].
    """
    if len(line) != 5:
        print('!!! ERROR: Invalid file')  # FIXME
        return
    time = line[0]
    qw = line[1]
    qx = line[2]
    qy = line[3]
    qz = line[4]
    eulerAngles = list(quat_to_euler(qw, qx, qy, qz, degrees=False))
    eulerAngles.insert(0, time)  # prepend time
    return eulerAngles
