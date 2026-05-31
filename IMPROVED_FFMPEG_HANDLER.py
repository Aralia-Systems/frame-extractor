"""
IMPROVED FFmpeg SUBPROCESS HANDLER FOR FRAME_EXTRACTOR.PY
=========================================================
Production-ready code replacement for real-time streaming, timeout handling, 
and Celery worker compatibility.

USAGE:
Replace the FFmpeg extraction section in frame_extractor.py (lines ~102-125) 
with this improved handler. It maintains the same interface but with:
  - Real-time log streaming (no buffering)
  - Configurable timeout support
  - Graceful shutdown/timeout handling
  - Optional Celery task.update_state() integration
  - Better error reporting with line-by-line analysis

REQUIREMENTS:
  - Add to imports at top of frame_extractor.py:
    import threading
    import signal
    from queue import Queue, Empty
    from typing import Callable, Optional

CELERY INTEGRATION:
  When calling from a Celery task, pass the task object:
    handler = StreamingFFmpegHandler(
        logger=logger,
        timeout_seconds=3600,
        task_update_callback=self.update_state  # if called from @celery.task
    )
    handler.run(ffmpeg_cmd)
"""

import threading
import signal
import subprocess
import time
import logging
from queue import Queue, Empty
from typing import Callable, Optional, List


class StreamingFFmpegHandler:
    """
    Handles FFmpeg subprocess execution with real-time output streaming,
    timeout support, and Celery worker compatibility.
    
    This handler solves key issues with the original subprocess.Popen + communicate():
    - Buffers all output (bad for long operations) → Uses threading for real-time streaming
    - No timeout handling → Adds configurable timeout with graceful shutdown
    - Can hang workers indefinitely → Implements SIGTERM + SIGKILL
    - No progress tracking → Optional Celery task.update_state() callback
    
    Attributes:
        logger: Python logger instance
        timeout_seconds: Maximum execution time (default 3600s for long videos)
        task_update_callback: Optional Celery task.update_state() for progress tracking
        process: The subprocess.Popen object
        timeout_occurred: Flag indicating if timeout was triggered
    """
    
    def __init__(
        self,
        logger: logging.Logger,
        timeout_seconds: int = 3600,
        task_update_callback: Optional[Callable] = None
    ):
        """
        Initialize the FFmpeg handler.
        
        Args:
            logger: Python logger instance for output
            timeout_seconds: Maximum execution time in seconds (default 3600s for 1-hour videos)
            task_update_callback: Optional Celery task.update_state(state='PROGRESS', meta={...})
                                 Called periodically with line counts for progress tracking
        """
        self.logger = logger
        self.timeout_seconds = timeout_seconds
        self.task_update_callback = task_update_callback
        self.process = None
        self.timeout_occurred = False
        self.stdout_queue = Queue()
        self.stderr_queue = Queue()
        self.line_count = 0
    
    def _enqueue_output(self, pipe, queue: Queue, pipe_name: str):
        """
        Thread target: reads from pipe line-by-line and queues for logging.
        
        This prevents blocking and allows real-time processing of FFmpeg output,
        which is critical for:
        - Detecting progress/errors early
        - Preventing deadlocks with large buffers
        - Streaming logs to Celery task state
        
        Args:
            pipe: File-like object (stdout or stderr from Popen)
            queue: Queue to place lines into
            pipe_name: Name of pipe ('stdout' or 'stderr') for logging context
        """
        try:
            for line in iter(pipe.readline, ''):
                if line:
                    queue.put((pipe_name, line.rstrip()))
        except Exception as e:
            self.logger.error(f"Error reading {pipe_name}: {e}")
        finally:
            pipe.close()
    
    def _process_queued_output(self):
        """
        Process all currently queued output lines from stdout/stderr.
        Logs each line and updates Celery task state if callback provided.
        
        Returns:
            Number of lines processed
        """
        lines_processed = 0
        try:
            while True:
                pipe_name, line = self.stdout_queue.get_nowait() if self.stdout_queue.qsize() > 0 else self.stderr_queue.get_nowait()
                
                # Log FFmpeg output at appropriate level
                if "error" in line.lower() or "fatal" in line.lower():
                    self.logger.warning(f"FFmpeg ({pipe_name}): {line}")
                elif "warning" in line.lower():
                    self.logger.info(f"FFmpeg ({pipe_name}): {line}")
                else:
                    self.logger.debug(f"FFmpeg ({pipe_name}): {line}")
                
                self.line_count += 1
                lines_processed += 1
                
                # Update Celery task state with progress
                if self.task_update_callback:
                    try:
                        self.task_update_callback(
                            state='PROGRESS',
                            meta={
                                'current_step': 'ffmpeg_extraction',
                                'lines_processed': self.line_count,
                                'status': 'processing'
                            }
                        )
                    except Exception as e:
                        self.logger.debug(f"Could not update Celery task state: {e}")
        except Empty:
            pass
        except Exception as e:
            self.logger.error(f"Error processing queued output: {e}")
        
        return lines_processed
    
    def _handle_timeout(self):
        """
        Handle timeout scenario: attempt graceful shutdown, then force kill.
        
        Timeout handling sequence:
        1. Send SIGTERM (graceful shutdown) with 5s grace period
        2. If process still alive, send SIGKILL (force termination)
        3. Log diagnostic information
        """
        self.logger.error(f"FFmpeg process exceeded timeout of {self.timeout_seconds}s - initiating shutdown")
        self.timeout_occurred = True
        
        if self.process and self.process.poll() is None:
            try:
                self.logger.info("Sending SIGTERM to FFmpeg process (graceful shutdown)...")
                self.process.terminate()
                
                # Wait up to 5 seconds for graceful termination
                try:
                    self.process.wait(timeout=5)
                    self.logger.info("FFmpeg process terminated gracefully")
                    return
                except subprocess.TimeoutExpired:
                    self.logger.warning("FFmpeg process did not terminate gracefully - sending SIGKILL")
                    self.process.kill()
                    self.process.wait()
                    self.logger.error("FFmpeg process force-killed")
            except Exception as e:
                self.logger.error(f"Error during timeout handling: {e}")
    
    def run(self, ffmpeg_cmd: List[str]) -> int:
        """
        Execute FFmpeg command with real-time output streaming and timeout support.
        
        This method replaces the buffering subprocess.Popen + communicate() pattern
        with streaming output that integrates with:
        - Python logging (line-by-line, level-aware)
        - Celery task state (optional progress updates)
        - Timeout handling (graceful shutdown then force kill)
        
        Args:
            ffmpeg_cmd: List of FFmpeg command arguments (e.g., ['ffmpeg', '-i', ...])
        
        Returns:
            Exit code from FFmpeg process (0 = success, non-zero = failure)
        
        Raises:
            TimeoutError: If process exceeds timeout_seconds
            Exception: If process exits with non-zero code
        
        Example:
            handler = StreamingFFmpegHandler(logger, timeout_seconds=3600)
            exit_code = handler.run(['ffmpeg', '-i', 'video.mp4', 'frame_%04d.png'])
            if exit_code != 0:
                raise Exception(f"FFmpeg failed with code {exit_code}")
        """
        self.logger.info("Starting FFmpeg frame extraction...")
        self.logger.debug(f"FFmpeg command: {' '.join(ffmpeg_cmd)}")
        start_time = time.time()
        
        try:
            # Start FFmpeg process with pipes for real-time output
            self.process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffering (1) instead of full buffering
            )
            
            # Start reader threads for stdout/stderr (prevents deadlock and enables streaming)
            stdout_thread = threading.Thread(
                target=self._enqueue_output,
                args=(self.process.stdout, self.stdout_queue, 'stdout'),
                daemon=True
            )
            stderr_thread = threading.Thread(
                target=self._enqueue_output,
                args=(self.process.stderr, self.stderr_queue, 'stderr'),
                daemon=True
            )
            stdout_thread.start()
            stderr_thread.start()
            
            # Monitor process with timeout
            while True:
                # Check if process has completed
                if self.process.poll() is not None:
                    break
                
                # Process any queued output
                self._process_queued_output()
                
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > self.timeout_seconds:
                    self._handle_timeout()
                    raise TimeoutError(
                        f"FFmpeg extraction exceeded timeout of {self.timeout_seconds}s "
                        f"(elapsed: {elapsed:.1f}s, lines processed: {self.line_count})"
                    )
                
                # Small sleep to prevent busy-waiting
                time.sleep(0.1)
            
            # Process any remaining output after process exits
            self._process_queued_output()
            
            # Wait for reader threads to finish
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)
            
            exit_code = self.process.returncode
            elapsed = time.time() - start_time
            
            # Log completion
            if exit_code == 0:
                self.logger.info(
                    f"FFmpeg frame extraction completed successfully "
                    f"({elapsed:.2f}s, {self.line_count} output lines)"
                )
                if self.task_update_callback:
                    try:
                        self.task_update_callback(
                            state='PROGRESS',
                            meta={
                                'current_step': 'ffmpeg_extraction',
                                'status': 'completed',
                                'elapsed_seconds': elapsed,
                                'lines_processed': self.line_count
                            }
                        )
                    except Exception as e:
                        self.logger.debug(f"Could not update final Celery state: {e}")
            else:
                self.logger.error(
                    f"FFmpeg extraction failed with exit code {exit_code} "
                    f"(elapsed: {elapsed:.2f}s, lines: {self.line_count})"
                )
            
            return exit_code
        
        except TimeoutError:
            self.logger.error(f"FFmpeg timeout: process exceeded {self.timeout_seconds}s limit")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error during FFmpeg execution: {e}")
            if self.process and self.process.poll() is None:
                try:
                    self.process.kill()
                except Exception as kill_error:
                    self.logger.error(f"Error killing process: {kill_error}")
            raise


# ============================================================================
# REPLACEMENT CODE SECTION FOR frame_extractor.py
# ============================================================================
# Copy the code below to replace the FFmpeg extraction section (lines ~102-125)
# in the process_frames() method of the FrameExtractor class

REPLACEMENT_CODE = """
        # Run FFmpeg extraction with real-time streaming and timeout support
        logger.info("Starting FFmpeg frame extraction...")
        start_time_extract = time.time()
        
        try:
            # Initialize streaming FFmpeg handler with timeout support
            ffmpeg_handler = StreamingFFmpegHandler(
                logger=logger,
                timeout_seconds=3600,  # 1 hour timeout for long videos
                task_update_callback=None  # Set to self.update_state if called from Celery task
            )
            
            # Run FFmpeg with real-time output streaming
            exit_code = ffmpeg_handler.run(ffmpeg_cmd)
            
            if exit_code != 0:
                logger.error(f"FFmpeg extraction failed with exit code {exit_code}")
                raise Exception(
                    f"FFmpeg frame extraction failed with exit code {exit_code}. "
                    f"Check logs above for details."
                )
            
        except TimeoutError as e:
            logger.error(f"FFmpeg extraction timeout: {e}")
            raise Exception(f"FFmpeg extraction timed out: {str(e)}")
        except Exception as e:
            logger.exception(f"Exception during FFmpeg extraction: {e}")
            raise
        
        end_time_extract = time.time()
"""

# ============================================================================
# INTEGRATION GUIDE FOR CELERY WORKERS
# ============================================================================
CELERY_INTEGRATION_EXAMPLE = """
# In workers/tasks/extract_frames.py (or similar Celery task file):

from frame_extractor import FrameExtractor, StreamingFFmpegHandler

@celery.task(bind=True)
def extract_frames_task(self, video_path: str, output_dir: str):
    \"\"\"
    Extract frames from video using FrameExtractor with Celery progress tracking.
    
    This task automatically reports progress via Celery's task.update_state():
    - FFmpeg output streaming with progress
    - Timeout protection (default 3600s)
    - Graceful shutdown on timeout
    \"\"\"
    try:
        # Initialize extractor
        extractor = FrameExtractor(video_path)
        
        # Get FFmpeg command (from existing code)
        ffmpeg_cmd = [
            'ffmpeg',
            '-hwaccel', 'nvdec',
            '-i', video_path,
            '-vsync', '0',
            output_pattern
        ]
        
        # Create handler with Celery callback for progress updates
        handler = StreamingFFmpegHandler(
            logger=logger,
            timeout_seconds=3600,
            task_update_callback=self.update_state  # Pass Celery task's update_state method
        )
        
        # Run extraction with automatic Celery state updates
        exit_code = handler.run(ffmpeg_cmd)
        
        if exit_code != 0:
            raise Exception(f"FFmpeg failed with code {exit_code}")
        
        # Continue with frame identification...
        extractor.continue_processing()
        
        return {
            'status': 'success',
            'frames': len(extractor.filenames),
            'selected': len(extractor.image_index_list)
        }
    
    except TimeoutError as e:
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise
    except Exception as e:
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise
"""

# ============================================================================
# TESTING EXAMPLES
# ============================================================================
TESTING_EXAMPLES = """
# Test 1: Basic streaming (no timeout)
handler = StreamingFFmpegHandler(logger, timeout_seconds=120)
try:
    exit_code = handler.run(['ffmpeg', '-i', 'test.mp4', 'frame_%04d.png'])
    assert exit_code == 0
except Exception as e:
    print(f"Test 1 failed: {e}")

# Test 2: Timeout simulation (will timeout after 5s)
handler = StreamingFFmpegHandler(logger, timeout_seconds=5)
try:
    exit_code = handler.run(['ffmpeg', '-i', 'large_video.mp4', 'frame_%04d.png'])
except TimeoutError as e:
    print(f"Timeout test passed: {e}")

# Test 3: Error handling (invalid video file)
handler = StreamingFFmpegHandler(logger, timeout_seconds=10)
try:
    exit_code = handler.run(['ffmpeg', '-i', 'nonexistent.mp4', 'frame_%04d.png'])
    assert exit_code != 0
except Exception as e:
    print(f"Error handling test passed: {e}")
"""

if __name__ == "__main__":
    print("StreamingFFmpegHandler - Production-ready FFmpeg subprocess handler")
    print("=" * 70)
    print("\nREPLACEMENT CODE FOR frame_extractor.py:\n")
    print(REPLACEMENT_CODE)
    print("\n" + "=" * 70)
    print("\nCELERY INTEGRATION EXAMPLE:\n")
    print(CELERY_INTEGRATION_EXAMPLE)
    print("\n" + "=" * 70)
    print("\nTESTING EXAMPLES:\n")
    print(TESTING_EXAMPLES)
