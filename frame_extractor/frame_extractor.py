import cv2
import os
import subprocess
import time
import logging
import numpy as np
from scipy.signal import argrelextrema
from typing import Tuple, List
import matplotlib.pyplot as plt

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create console handler with DEBUG level
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# Magic number constants
FRAME_INDEX_MASK = [-3, 0, 3, 6, 9, 12]
ARGRELEXTREMA_ORDER = 12
MAX_IMAGES_LIMIT = 100
REFERENCE_FRAME_OFFSET = 2
FRAME_NAME_PREFIX = "frame_"
FRAME_FILE_EXTENSION = ".png"
FFMPEG_TIMEOUT_SECONDS = 120

class FrameExtractor:
    """
    A class for processing frames from a video using FFmpeg and OpenCV.

    Args:
        input_video_filepath (str): The path to the input video file.
        use_hw_acceleration (bool): Enable NVIDIA hardware acceleration (NVDEC).
            Default: True. Set to False to use CPU-only processing.

    Attributes:
        input_video_path (str): The path to the input video file.
        image_folder_path (str): The folder where extracted frames will be saved.
        image_index_list (list): A list of frame indices selected for further processing.
        filenames (list): List of all extracted frame filenames.
        mean_intensity (list): Mean intensity values for each frame.
        use_hw_acceleration (bool): Whether hardware acceleration is enabled.

    Methods:
        _read_image_strict(image_path: str, flags: int = cv2.IMREAD_COLOR) -> np.ndarray:
            Read an image and raise an exception if loading fails.

        _detect_sync_errors_and_shift_frame_indices() -> None:
            Detect potential frame synchronization anomalies for selected frames.

        process_frames() -> Tuple[float, float]:
            Process frames from the input video and save them as PNG images.
            Also generates an intensity histogram for analysis.
            Returns extraction time and identification time in seconds.

        get_image_index_list() -> List[int]:
            Get the list of frame indices selected for processing.

        get_filenames_to_process() -> List[str]:
            Get filenames that should be processed based on selected indices.

        cleanup() -> None:
            Delete temporary frame files that were not selected for processing.
    """

    def __init__(self, input_video_filepath: str, use_hw_acceleration: bool = True) -> None:
        logger.info(f"Initializing FrameExtractor with video: {input_video_filepath}")
        self.input_video_path = input_video_filepath
        self.image_folder_path = os.path.dirname(input_video_filepath)
        self.image_index_list = []
        self.filenames = []
        self._extracted_filenames = []
        self.mean_intensity = []
        self._processed = False
        self.use_hw_acceleration = use_hw_acceleration
        logger.debug(f"Output folder path set to: {self.image_folder_path}")
        logger.debug(f"Hardware acceleration: {'enabled' if use_hw_acceleration else 'disabled'}")

    def __enter__(self):
        """Enable context manager support for automatic resource cleanup."""
        logger.debug("Entering FrameExtractor context")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup temporary frame files on context exit."""
        logger.debug("Exiting FrameExtractor context")
        self.cleanup()
        return False

    def _read_image_strict(self, image_path: str, flags: int = cv2.IMREAD_COLOR) -> np.ndarray:
        """
        Read an image file strictly. Raises an exception if the image cannot be read.
        
        Args:
            image_path (str): Path to the image file.
            flags (int): OpenCV imread flags (e.g., cv2.IMREAD_COLOR, cv2.IMREAD_GRAYSCALE).
            
        Returns:
            np.ndarray: The loaded image.
            
        Raises:
            Exception: If cv2.imread fails to load the image.
        """
        img = cv2.imread(image_path, flags)
        if img is None:
            logger.error(f"CRITICAL: Failed to read image {image_path}")
            raise Exception(f"Failed to read image {os.path.basename(image_path)}. Video extraction may be corrupted.")
        return img

    def process_frames(self) -> Tuple[float, float]:
        """
        Process frames from the input video and save them as PNG images.

        Returns:
            Tuple[float, float]: (extraction_time, identification_time) in seconds.

        Raises:
            Exception: If FFmpeg exits with a non-zero status.
            Exception: If FFmpeg frame extraction times out.
            Exception: If no new frames are extracted.
            Exception: If extracted frame count exceeds MAX_IMAGES_LIMIT.
            Exception: If no suitable reference frame can be identified.
            Exception: If any frame fails to read.
            Exception: Propagated from _check_indices_in_range when selected indices
                fall outside the valid range.
        """
        logger.info(f"Starting frame processing for video: {self.input_video_path}")
        
        # Construct FFmpeg command for frame extraction
        output_pattern = os.path.join(self.image_folder_path, f'{FRAME_NAME_PREFIX}%04d{FRAME_FILE_EXTENSION}')
        
        # Build command with optional hardware acceleration
        ffmpeg_cmd = ['ffmpeg']
        
        if self.use_hw_acceleration:
            ffmpeg_cmd.extend(['-hwaccel', 'nvdec'])
        
        ffmpeg_cmd.extend([
            '-i', self.input_video_path,
            '-vsync', '0',
            output_pattern
        ])
        
        logger.debug(f"FFmpeg command: {' '.join(ffmpeg_cmd)}")

        # Run FFmpeg extraction
        logger.info("Starting FFmpeg frame extraction...")
        start_time_extract = time.time()
        try:
            # Snapshot existing frame files so stale files do not affect this run.
            existing_frame_files = {
                f for f in os.listdir(self.image_folder_path)
                if f.endswith(FRAME_FILE_EXTENSION) and f.startswith(FRAME_NAME_PREFIX)
            }
            process = subprocess.Popen(ffmpeg_cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate(timeout=FFMPEG_TIMEOUT_SECONDS)
            exit_code = process.returncode
            
            if stdout:
                logger.debug(f"FFmpeg stdout: {stdout}")
            if stderr:
                logger.debug(f"FFmpeg stderr: {stderr}")
                
            if exit_code != 0:
                logger.error(f"FFmpeg extraction failed with exit code {exit_code}")
                logger.error(f"Error details: {stderr}")
                raise Exception(f"FFmpeg frame extraction failed with exit code {exit_code}. Details: {stderr}")
            
            logger.info("FFmpeg frame extraction completed successfully")
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            logger.error(f"FFmpeg extraction timed out after {FFMPEG_TIMEOUT_SECONDS} seconds")
            logger.error(f"Partial FFmpeg output. stdout: {stdout}, stderr: {stderr}")
            raise Exception(f"FFmpeg frame extraction timed out after {FFMPEG_TIMEOUT_SECONDS} seconds")
        except Exception as e:
            logger.exception(f"Exception during FFmpeg extraction: {e}")
            raise
        end_time_extract = time.time()

        # Initialize variables for frame analysis
        difference = []
        frame_n1 = None
        start_range = 0
        num_of_images = 0
    
        logger.info("Starting frame identification and analysis...")
        start_time_identify = time.time()
        
        # Get newly extracted frame files sorted by name.
        all_files = sorted(os.listdir(self.image_folder_path))
        frame_files = [
            f for f in all_files
            if f.endswith(FRAME_FILE_EXTENSION)
            and f.startswith(FRAME_NAME_PREFIX)
            and f not in existing_frame_files
        ]
        logger.info(f"Found {len(frame_files)} frame files to process")
        self._extracted_filenames = list(frame_files)

        if not frame_files:
            logger.error("No frames were extracted by FFmpeg")
            raise Exception("Frame extraction produced no frames.")
        
        if len(frame_files) > MAX_IMAGES_LIMIT:
            logger.error(f"Too many frames found ({len(frame_files)}) - FFmpeg extraction may have failed")
            raise Exception(f"Frame extraction produced too many frames ({len(frame_files)} > {MAX_IMAGES_LIMIT}). Something went wrong.")
        
        # Iterate through extracted frames to analyze intensity changes
        for idx, filename in enumerate(frame_files):
            image_path = os.path.join(self.image_folder_path, filename)
            logger.debug(f"Processing frame {idx + 1}/{len(frame_files)}: {filename}")
            
            # Read the frame strictly as grayscale. No silent skipping.
            frame = self._read_image_strict(image_path, cv2.IMREAD_GRAYSCALE)
                
            if frame_n1 is not None:
                mean_val = np.mean(frame)
                self.mean_intensity.append(mean_val)
                diff = np.mean(abs(frame_n1.astype(float) - frame.astype(float)))
                difference.append(diff)
                logger.debug(f"Frame {filename}: mean_intensity={mean_val:.2f}, diff_from_prev={diff:.2f}")
            else:
                self.mean_intensity.append(0)
                logger.debug(f"First frame {filename}: skipping difference calculation")

            frame_n1 = frame
            num_of_images += 1
            self.filenames.append(filename)
        
        logger.info(f"Frame identification complete: processed {num_of_images} frames")

        process_range = (start_range, num_of_images)
        logger.info(f"Process range: {process_range}")

        # Calculate local maxima in intensity differences using rolling mean
        logger.debug("Calculating intensity differences with rolling mean...")
        rolled_mean = np.roll(self.mean_intensity, 2)
        diff_2 = self.mean_intensity - rolled_mean
        logger.debug(f"Rolled mean differences: {diff_2}")
        
        # Find local maxima in the difference signal
        maximal_diff2 = np.asarray(argrelextrema(diff_2, np.greater, order=ARGRELEXTREMA_ORDER))
        maximal_diff2 = np.concatenate(maximal_diff2)
        logger.info(f"Found {len(maximal_diff2)} local maxima at indices: {maximal_diff2}")
        logger.debug(f"Intensity differences at maxima: {diff_2[maximal_diff2] if len(maximal_diff2) > 0 else 'N/A'}")

        end_time_identify = time.time()

        # Select reference frame based on detected cycles
        logger.info(f"Selecting reference frame from {len(maximal_diff2)} detected cycles...")
        if len(maximal_diff2) > REFERENCE_FRAME_OFFSET:
            current_value = maximal_diff2[REFERENCE_FRAME_OFFSET]
            logger.info(f"Selected frame index {current_value} as reference (cycle {REFERENCE_FRAME_OFFSET})")
        elif len(maximal_diff2) == 1:
            current_value = maximal_diff2[0]
            logger.warning(f"Only 1 cycle detected; using frame index {current_value} as reference")
        else:
            logger.error(f"Failed to find suitable reference frame: only {len(maximal_diff2)} cycle(s) detected")
            raise Exception(f"Failed to find reference frame: insufficient cycles detected ({len(maximal_diff2)}). Expected at least {REFERENCE_FRAME_OFFSET}.")

        # Calculate processing times
        extract_time = end_time_extract - start_time_extract
        identify_time = end_time_identify - start_time_identify
        logger.info(f"Processing times - Extraction: {extract_time:.2f}s, Identification: {identify_time:.2f}s")

        # Get frame indices within valid range around reference frame
        self.image_index_list = self._check_indices_in_range(current_value, process_range)
        logger.info(f"Selected frame indices: {self.image_index_list}")

        # Detect and handle sync errors
        self._detect_sync_errors_and_shift_frame_indices()
        
        self._processed = True
        logger.info(f"Frame processing complete. Returning extraction_time={extract_time:.2f}s, identify_time={identify_time:.2f}s")
        
        # Generate intensity histogram
        self._plot_intensity_histogram()
        
        return extract_time, identify_time
    
    def _check_indices_in_range(self, reference_frame: int, image_range: Tuple[int, int]) -> List[int]:
        """
        Calculate frame indices around a reference frame using a predefined mask.
        """
        logger.debug(f"Calculating indices around reference frame {reference_frame} with range {image_range}")
        masked_list = [x + reference_frame for x in FRAME_INDEX_MASK]
        logger.debug(f"Masked indices: {masked_list}")
        
        all_in_range = all(start_idx >= image_range[0] and start_idx < image_range[1] for start_idx in masked_list)

        if all_in_range:
            logger.info(f"All indices within valid range {image_range}: {masked_list}")
            return masked_list
        else:
            out_of_range = [idx for idx in masked_list if idx < image_range[0] or idx >= image_range[1]]
            logger.error(f"Frame indices out of bounds. Invalid indices: {out_of_range}, valid range: {image_range}")
            raise Exception(f"Frame indices out of bounds: {out_of_range} not in range {image_range}")

    def _detect_sync_errors_and_shift_frame_indices(self) -> None:
        """
        Detect potential frame synchronization errors by analyzing mean differences between selected frames.
        Raises an exception if any frame fails to read.
        """
        logger.debug("Checking for frame synchronization errors...")
        
        min_index = min(self.image_index_list)
        max_index = self.image_index_list[REFERENCE_FRAME_OFFSET]
        sequence_to_process = [self.filenames[x] for x in range(min_index, max_index + 1)]
        logger.debug(f"Sync check sequence indices: {min_index} to {max_index}, files: {sequence_to_process}")
        
        img_n1 = None
        mean_diff_list = []
        
        for i, image in enumerate(sequence_to_process):
            image_path = os.path.join(self.image_folder_path, image)
            
            # Read the image strictly (default is color). No silent skipping.
            img = self._read_image_strict(image_path)
                
            if img_n1 is not None:
                mean_diff = np.mean(img.astype(float) - img_n1.astype(float))
                mean_diff_list.append(mean_diff)
                logger.debug(f"Sync frame {i}: {image} - mean_diff={mean_diff:.2f}")
            img_n1 = img

        logger.debug(f"Mean differences in sequence: {mean_diff_list}")

        # Analyze frame differences for sync anomalies
        if len(mean_diff_list) >= 2:
            if mean_diff_list[1] > mean_diff_list[0]:
                count_less_than_index_1 = sum(value < mean_diff_list[1] for value in mean_diff_list[2:])
                if count_less_than_index_1 > 1:
                    logger.warning("Frame sync anomaly detected: may need reindexing")
                else:
                    logger.info("Frame indices confirmed valid - no reindexing needed")
            else:
                logger.warning("Possible frame sync issue detected: index[1] not greater than index[0]")
        else:
            logger.debug(f"Insufficient data for sync check ({len(mean_diff_list)} differences)")

    def _plot_intensity_histogram(self) -> None:
        """
        Generate and save a plot of mean intensity values across frames.
        """
        if not self.mean_intensity or not self.image_index_list:
            logger.debug("Skipping plot: insufficient data")
            return
        
        try:
            selected_intensity = [self.mean_intensity[idx] for idx in self.image_index_list]
            selected_frame_numbers = self.image_index_list
            all_frame_numbers = list(range(len(self.mean_intensity)))
            
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
            
            ax1.plot(all_frame_numbers, self.mean_intensity, 
                    marker='o', linestyle='-', linewidth=1.5, markersize=4, 
                    color='steelblue', label='Frame Intensity')
            ax1.axhline(np.mean(self.mean_intensity), color='red', linestyle='--', 
                       linewidth=2, label=f'Mean: {np.mean(self.mean_intensity):.2f}')
            ax1.set_xlabel('Frame Number', fontsize=11)
            ax1.set_ylabel('Mean Intensity', fontsize=11)
            ax1.set_title('All Extracted Frames', fontsize=12, fontweight='bold')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            ax2.plot(selected_frame_numbers, selected_intensity, 
                    marker='o', linestyle='-', linewidth=1.5, markersize=6, 
                    color='forestgreen', label='Selected Intensity')
            ax2.axhline(np.mean(selected_intensity), color='red', linestyle='--', 
                       linewidth=2, label=f'Mean: {np.mean(selected_intensity):.2f}')
            ax2.set_xlabel('Frame Number', fontsize=11)
            ax2.set_ylabel('Mean Intensity', fontsize=11)
            ax2.set_title(f'Selected Frames (n={len(selected_intensity)})', fontsize=12, fontweight='bold')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
            fig.suptitle('Frame Intensity Analysis', fontsize=14, fontweight='bold', y=1.00)
            fig.tight_layout()
            
            histogram_path = os.path.join(self.image_folder_path, 'intensity_histogram.png')
            fig.savefig(histogram_path, dpi=100, bbox_inches='tight')
            logger.info(f"Intensity plot saved: {histogram_path}")
            
            plt.close(fig)
            
        except Exception as e:
            logger.warning(f"Error generating intensity plot: {e}")

    def cleanup(self) -> None:
        """
        Delete temporary frame files that were not selected for processing.
        """
        if not self._processed and not self._extracted_filenames:
            logger.debug("Cleanup called before processing; nothing to clean")
            return
        
        try:
            if self._processed:
                filenames_to_delete = [
                    self.filenames[x] for x in range(len(self.filenames))
                    if x not in self.image_index_list
                ]
            else:
                # If processing failed partway through, remove only files created in this run.
                filenames_to_delete = list(self._extracted_filenames)
            
            if not filenames_to_delete:
                logger.info("No files to delete; all frames were selected")
                return
            
            logger.info(f"Cleaning up {len(filenames_to_delete)} temporary frame files")
            for filename in filenames_to_delete:
                filepath = os.path.join(self.image_folder_path, filename)
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        logger.debug(f"Deleted: {filename}")
                    else:
                        logger.debug(f"File not found for deletion: {filename}")
                except Exception as e:
                    logger.warning(f"Failed to delete {filename}: {e}")
            self._extracted_filenames = []
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def get_image_index_list(self) -> List[int]:
        """
        Get the list of frame indices selected for processing.
        """
        logger.debug(f"Getting image index list: {self.image_index_list}")
        if not self.image_index_list:
            logger.error("Attempted to get image_index_list before process_frames() was called")
            raise Exception("image_index_list is empty. Call process_frames() first.")
        return self.image_index_list

    def get_filenames_to_process(self) -> List[str]:
        """
        Get filenames corresponding to selected frame indices.
        """
        logger.debug("Getting filenames to process")
        if not self.image_index_list:
            logger.error("Attempted to get filenames before process_frames() was called")
            raise Exception("image_index_list is empty. Call process_frames() first.")
        if not self.filenames:
            logger.error("Filenames list is empty")
            raise Exception("filenames list is empty. Call process_frames() first.")
        filenames_to_process = [self.filenames[x] for x in self.image_index_list]
        logger.info(f"Returning {len(filenames_to_process)} filenames to process: {filenames_to_process}")
        return filenames_to_process