"""
Shared utilities for chessboard pattern detection and processing.

This module provides common functions used by both the chessboard pose tracker
and camera calibration service.
"""

import base64
import cv2
import numpy as np
from typing import Optional, Tuple


def detect_chessboard_corners(
    image: np.ndarray,
    pattern_size: Tuple[int, int]
) -> Optional[np.ndarray]:
    """Detect and refine chessboard corners in an image.

    Args:
        image: Input image (grayscale or color)
        pattern_size: Dimensions of the chessboard pattern (width, height) as number of inner corners

    Returns:
        Refined corner locations as (N, 1, 2) array, or None if not found

    Note:
        OpenCV's findChessboardCorners returns corners in a consistent order:
        - Starts from one corner and proceeds row by row
        - The starting corner is determined by the chessboard orientation in the image
        - For consistent corner numbering across multiple views (e.g., for hand-eye calibration),
          ensure the chessboard maintains the same orientation relative to the camera
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image

    # Find chessboard corners
    found, corners = cv2.findChessboardCorners(
        gray,
        pattern_size,
        flags=cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
    )

    if not found:
        return None

    # Refine corner locations to sub-pixel precision
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

    return corners


def generate_object_points(
    pattern_size: Tuple[int, int],
    square_size: float
) -> np.ndarray:
    """Generate 3D object points for the chessboard pattern.

    Args:
        pattern_size: Dimensions of the chessboard pattern (width, height) as number of inner corners
        square_size: Physical size of a square in the chessboard pattern (in mm or other units)

    Returns:
        Object points as (N, 3) array where N is number of corners
    """
    objp = np.zeros((pattern_size[1] * pattern_size[0], 3), np.float32)
    objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)
    objp *= square_size
    return objp


def decode_base64_image(base64_str: str) -> np.ndarray:
    """Decode a base64 encoded image string to a numpy array.

    Args:
        base64_str: Base64 encoded image string (with or without data URI prefix)

    Returns:
        Image as numpy array in RGB format
    """
    # Remove data URI prefix if present
    if ',' in base64_str:
        base64_str = base64_str.split(',', 1)[1]

    # Decode base64 string
    img_bytes = base64.b64decode(base64_str)

    # Convert to numpy array
    nparr = np.frombuffer(img_bytes, np.uint8)

    # Decode image
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # Convert from BGR to RGB (OpenCV loads as BGR)
    if image is not None and len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    return image
