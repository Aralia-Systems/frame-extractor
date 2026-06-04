"""
Pytest configuration and fixtures for frame-extractor tests.
"""

import pytest
import tempfile
import shutil
import os
import cv2
import numpy as np
from pathlib import Path


@pytest.fixture
def temp_video_dir():
    """Create a temporary directory for test videos."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_video_path(temp_video_dir):
    """
    Create a simple test video file.
    
    Creates a 2-second video with 30 frames at 15 FPS showing intensity changes.
    """
    video_path = os.path.join(temp_video_dir, "test_video.mp4")
    
    # Video parameters
    width, height = 640, 480
    fps = 15
    duration_frames = 30  # 2 seconds at 15 FPS
    
    # Create video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(video_path, fourcc, fps, (width, height))
    
    if not out.isOpened():
        pytest.skip("VideoWriter failed; FFmpeg might not be installed")
    
    # Create frames with intensity patterns (simulating exposure changes)
    # This creates 5 intensity cycles
    frames_per_cycle = 6
    num_cycles = 5
    
    try:
        for frame_idx in range(duration_frames):
            cycle_pos = (frame_idx % frames_per_cycle) / frames_per_cycle
            # Create sine wave intensity pattern
            intensity = int(128 + 127 * np.sin(2 * np.pi * cycle_pos))
            
            # Create frame with solid color
            frame = np.full((height, width, 3), intensity, dtype=np.uint8)
            
            # Add some variation to avoid uniform frames
            noise = np.random.randint(0, 20, (height, width, 3), dtype=np.uint8)
            frame = cv2.add(frame, noise)
            
            out.write(frame)
        
        out.release()
    except Exception as e:
        out.release()
        raise e
    
    return video_path


@pytest.fixture
def output_dir(temp_video_dir):
    """Create output directory for extracted frames."""
    output_dir = os.path.join(temp_video_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


@pytest.fixture
def video_with_output_dir(temp_video_dir, output_dir):
    """Create a test video in the output directory."""
    video_path = os.path.join(output_dir, "test_video.mp4")
    
    # Video parameters
    width, height = 640, 480
    fps = 15
    duration_frames = 30
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(video_path, fourcc, fps, (width, height))
    
    if not out.isOpened():
        pytest.skip("VideoWriter failed; FFmpeg might not be installed")
    
    try:
        for frame_idx in range(duration_frames):
            cycle_pos = (frame_idx % 6) / 6
            intensity = int(128 + 127 * np.sin(2 * np.pi * cycle_pos))
            frame = np.full((height, width, 3), intensity, dtype=np.uint8)
            noise = np.random.randint(0, 20, (height, width, 3), dtype=np.uint8)
            frame = cv2.add(frame, noise)
            out.write(frame)
        
        out.release()
    except Exception as e:
        out.release()
        raise e
    
    return video_path, output_dir
