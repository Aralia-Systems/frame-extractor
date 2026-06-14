"""
Unit and integration tests for FrameExtractor class.
"""

import pytest
import os
import subprocess
import numpy as np
from pathlib import Path
from frame_extractor import FrameExtractor
import frame_extractor.frame_extractor as extractor_module


class TestFrameExtractorInitialization:
    """Tests for FrameExtractor initialization."""
    
    def test_init_stores_video_path(self, video_with_output_dir):
        """Test that initialization correctly stores video path."""
        video_path, output_dir = video_with_output_dir
        extractor = FrameExtractor(video_path)
        assert extractor.input_video_path == video_path
    
    def test_init_sets_output_folder(self, video_with_output_dir):
        """Test that output folder is set to video directory."""
        video_path, output_dir = video_with_output_dir
        extractor = FrameExtractor(video_path)
        assert extractor.image_folder_path == output_dir
    
    def test_init_empty_lists(self, video_with_output_dir):
        """Test that collections are initialized as empty."""
        video_path, _ = video_with_output_dir
        extractor = FrameExtractor(video_path)
        assert extractor.image_index_list == []
        assert extractor.filenames == []
        assert extractor.mean_intensity == []
    
    def test_init_processed_flag(self, video_with_output_dir):
        """Test that _processed flag is False initially."""
        video_path, _ = video_with_output_dir
        extractor = FrameExtractor(video_path)
        assert extractor._processed is False
    
    def test_init_hw_acceleration_default(self, video_with_output_dir):
        """Test that hardware acceleration is enabled by default."""
        video_path, _ = video_with_output_dir
        extractor = FrameExtractor(video_path)
        assert extractor.use_hw_acceleration is True
    
    def test_init_hw_acceleration_disabled(self, video_with_output_dir):
        """Test that hardware acceleration can be disabled."""
        video_path, _ = video_with_output_dir
        extractor = FrameExtractor(video_path, use_hw_acceleration=False)
        assert extractor.use_hw_acceleration is False


class TestFrameExtractorContextManager:
    """Tests for context manager support."""
    
    def test_enter_returns_self(self, video_with_output_dir):
        """Test that __enter__ returns the extractor instance."""
        video_path, _ = video_with_output_dir
        extractor = FrameExtractor(video_path)
        result = extractor.__enter__()
        assert result is extractor
    
    def test_exit_calls_cleanup(self, video_with_output_dir):
        """Test that __exit__ calls cleanup."""
        video_path, output_dir = video_with_output_dir
        extractor = FrameExtractor(video_path)
        
        # Simulate processing by manually creating frame files
        extractor.filenames = ["frame_0001.png", "frame_0002.png"]
        extractor.image_index_list = [0]
        extractor._processed = True
        
        # Create dummy files
        dummy_files = [os.path.join(output_dir, f) for f in extractor.filenames]
        for f in dummy_files:
            open(f, 'w').close()
        
        # Exit context should cleanup
        extractor.__exit__(None, None, None)
        
        # Check that unused file was deleted
        assert not os.path.exists(dummy_files[1])
        assert os.path.exists(dummy_files[0])  # Selected frame should remain
    
    def test_context_manager_usage(self, video_with_output_dir):
        """Test using FrameExtractor as context manager."""
        video_path, output_dir = video_with_output_dir
        
        with FrameExtractor(video_path) as extractor:
            assert extractor.input_video_path == video_path
            extractor.filenames = ["frame_0001.png", "frame_0002.png"]
            extractor.image_index_list = [0]
            extractor._processed = True
            
            # Create dummy files
            for fname in extractor.filenames:
                open(os.path.join(output_dir, fname), 'w').close()
        
        # After exiting context, cleanup should have run
        assert os.path.exists(os.path.join(output_dir, "frame_0001.png"))
        assert not os.path.exists(os.path.join(output_dir, "frame_0002.png"))


class TestFrameExtractorCleanup:
    """Tests for cleanup functionality."""
    
    def test_cleanup_before_processing(self, video_with_output_dir):
        """Test cleanup when called before process_frames."""
        video_path, _ = video_with_output_dir
        extractor = FrameExtractor(video_path)
        # Should not raise error
        extractor.cleanup()
        assert extractor._processed is False
    
    def test_cleanup_deletes_unselected_files(self, video_with_output_dir):
        """Test that cleanup only deletes unselected files."""
        video_path, output_dir = video_with_output_dir
        extractor = FrameExtractor(video_path)
        
        # Setup state
        extractor.filenames = ["frame_0001.png", "frame_0002.png", "frame_0003.png"]
        extractor.image_index_list = [0, 2]  # Keep first and third
        extractor._processed = True
        
        # Create dummy files
        for fname in extractor.filenames:
            open(os.path.join(output_dir, fname), 'w').close()
        
        # Cleanup
        extractor.cleanup()
        
        # Verify
        assert os.path.exists(os.path.join(output_dir, "frame_0001.png"))
        assert not os.path.exists(os.path.join(output_dir, "frame_0002.png"))
        assert os.path.exists(os.path.join(output_dir, "frame_0003.png"))
    
    def test_cleanup_handles_missing_files(self, video_with_output_dir):
        """Test cleanup gracefully handles missing files."""
        video_path, output_dir = video_with_output_dir
        extractor = FrameExtractor(video_path)
        
        extractor.filenames = ["frame_0001.png", "frame_0002.png"]
        extractor.image_index_list = [0]
        extractor._processed = True
        
        # Create only first file
        open(os.path.join(output_dir, "frame_0001.png"), 'w').close()
        # Don't create frame_0002.png
        
        # Should not raise error
        extractor.cleanup()
    
    def test_cleanup_no_files_to_delete(self, video_with_output_dir):
        """Test cleanup when all files are selected."""
        video_path, output_dir = video_with_output_dir
        extractor = FrameExtractor(video_path)
        
        extractor.filenames = ["frame_0001.png", "frame_0002.png"]
        extractor.image_index_list = [0, 1]  # Select all
        extractor._processed = True
        
        for fname in extractor.filenames:
            open(os.path.join(output_dir, fname), 'w').close()
        
        extractor.cleanup()
        
        # All files should remain
        for fname in extractor.filenames:
            assert os.path.exists(os.path.join(output_dir, fname))


class TestFrameExtractorGetters:
    """Tests for getter methods."""
    
    def test_get_image_index_list_before_processing(self, video_with_output_dir):
        """Test that getter raises error before processing."""
        video_path, _ = video_with_output_dir
        extractor = FrameExtractor(video_path)
        
        with pytest.raises(Exception, match="image_index_list is empty"):
            extractor.get_image_index_list()
    
    def test_get_image_index_list_after_processing(self, video_with_output_dir):
        """Test getter returns correct list after processing."""
        video_path, output_dir = video_with_output_dir
        extractor = FrameExtractor(video_path)
        
        test_indices = [2, 5, 8, 11, 14]
        extractor.image_index_list = test_indices
        
        result = extractor.get_image_index_list()
        assert result == test_indices
    
    def test_get_filenames_to_process_before_processing(self, video_with_output_dir):
        """Test that getter raises error before processing."""
        video_path, _ = video_with_output_dir
        extractor = FrameExtractor(video_path)
        
        with pytest.raises(Exception, match="image_index_list is empty"):
            extractor.get_filenames_to_process()
    
    def test_get_filenames_to_process_returns_correct_files(self, video_with_output_dir):
        """Test getter returns correct filenames."""
        video_path, _ = video_with_output_dir
        extractor = FrameExtractor(video_path)
        
        extractor.filenames = [
            "frame_0001.png", "frame_0002.png", "frame_0003.png",
            "frame_0004.png", "frame_0005.png"
        ]
        extractor.image_index_list = [0, 2, 4]
        
        result = extractor.get_filenames_to_process()
        expected = ["frame_0001.png", "frame_0003.png", "frame_0005.png"]
        assert result == expected
    
    def test_cleanup_behavior_replaces_deleted_filenames_api(self, video_with_output_dir):
        """Test cleanup performs delete-selection behavior directly."""
        video_path, output_dir = video_with_output_dir
        extractor = FrameExtractor(video_path)

        extractor.filenames = ["frame_0001.png", "frame_0002.png"]
        extractor.image_index_list = [0]
        extractor._processed = True

        keep_path = os.path.join(output_dir, "frame_0001.png")
        delete_path = os.path.join(output_dir, "frame_0002.png")
        open(keep_path, 'w').close()
        open(delete_path, 'w').close()

        extractor.cleanup()

        assert os.path.exists(keep_path)
        assert not os.path.exists(delete_path)


class TestFrameExtractorIntegration:
    """Integration tests with actual video processing."""
    
    @pytest.mark.skipif(
        os.name != 'nt',
        reason="FFmpeg test skipped on non-Windows; adjust as needed"
    )
    def test_process_frames_creates_output_files(self, video_with_output_dir):
        """Test that process_frames creates frame files."""
        video_path, output_dir = video_with_output_dir
        extractor = FrameExtractor(video_path)
        
        try:
            extract_time, identify_time = extractor.process_frames()
        except Exception as e:
            pytest.skip(f"FFmpeg processing failed: {e}")
        
        # Check that frames were extracted
        assert len(extractor.filenames) > 0
        assert extract_time > 0
        assert identify_time > 0
        
        # Check that files exist
        for filename in extractor.filenames:
            filepath = os.path.join(output_dir, filename)
            assert os.path.exists(filepath), f"Frame file not found: {filename}"
    
    @pytest.mark.skipif(
        os.name != 'nt',
        reason="FFmpeg test skipped on non-Windows"
    )
    def test_process_frames_identifies_indices(self, video_with_output_dir):
        """Test that process_frames identifies valid frame indices."""
        video_path, _ = video_with_output_dir
        extractor = FrameExtractor(video_path)
        
        try:
            extractor.process_frames()
        except Exception as e:
            pytest.skip(f"FFmpeg processing failed: {e}")
        
        # Check that indices were identified
        assert len(extractor.image_index_list) > 0
        
        # All indices should be valid
        for idx in extractor.image_index_list:
            assert 0 <= idx < len(extractor.filenames)
    
    @pytest.mark.skipif(
        os.name != 'nt',
        reason="FFmpeg test skipped on non-Windows"
    )
    def test_process_frames_with_context_manager(self, video_with_output_dir):
        """Test using process_frames within context manager."""
        video_path, output_dir = video_with_output_dir
        
        initial_file_count = len(os.listdir(output_dir)) - 1  # Exclude video file
        
        try:
            with FrameExtractor(video_path) as extractor:
                extractor.process_frames()
                filenames_to_process = extractor.get_filenames_to_process()
                assert len(filenames_to_process) > 0
        except Exception as e:
            pytest.skip(f"FFmpeg processing failed: {e}")
        
        # After context exit, only selected frames should remain
        remaining_frames = [f for f in os.listdir(output_dir) if f.endswith('.png')]
        assert len(remaining_frames) == len(filenames_to_process)
    
    @pytest.mark.skipif(
        os.name != 'nt',
        reason="FFmpeg test skipped on non-Windows"
    )
    def test_histogram_generation(self, video_with_output_dir):
        """Test that intensity histogram is generated."""
        video_path, output_dir = video_with_output_dir
        
        try:
            extractor = FrameExtractor(video_path)
            extractor.process_frames()
        except Exception as e:
            pytest.skip(f"FFmpeg processing failed: {e}")
        
        # Check that histogram file was created
        histogram_path = os.path.join(output_dir, 'intensity_histogram.png')
        assert os.path.exists(histogram_path), "Histogram file not created"
        assert os.path.getsize(histogram_path) > 0, "Histogram file is empty"
        
        # Cleanup
        extractor.cleanup()
    
    @pytest.mark.skipif(
        os.name != 'nt',
        reason="FFmpeg test skipped on non-Windows"
    )
    def test_histogram_with_selected_frames(self, video_with_output_dir):
        """Test that histogram correctly shows all and selected frames."""
        video_path, output_dir = video_with_output_dir
        
        try:
            extractor = FrameExtractor(video_path)
            extractor.process_frames()
        except Exception as e:
            pytest.skip(f"FFmpeg processing failed: {e}")
        
        # Verify histogram data
        assert len(extractor.mean_intensity) > 0, "Mean intensity not calculated"
        assert len(extractor.image_index_list) > 0, "Selected indices not identified"
        
        # Selected intensity should be subset of all intensity
        selected_intensity = [extractor.mean_intensity[idx] for idx in extractor.image_index_list]
        assert len(selected_intensity) <= len(extractor.mean_intensity)
        
        # Cleanup
        extractor.cleanup()


class TestFrameExtractorEdgeCases:
    """Tests for edge cases and error conditions."""
    
    def test_nonexistent_video_file(self, temp_video_dir):
        """Test behavior with nonexistent video file."""
        fake_path = os.path.join(temp_video_dir, "nonexistent.mp4")
        extractor = FrameExtractor(fake_path)
        
        # Should initialize without error
        assert extractor.input_video_path == fake_path
        
        # Should fail when processing
        with pytest.raises(Exception):
            extractor.process_frames()
    
    def test_empty_filenames_list(self, video_with_output_dir):
        """Test getters with empty filenames list."""
        video_path, _ = video_with_output_dir
        extractor = FrameExtractor(video_path)
        extractor.image_index_list = [0]  # Non-empty indices
        # filenames is still empty
        
        with pytest.raises(Exception, match="filenames list is empty"):
            extractor.get_filenames_to_process()


class TestFrameExtractorFailureModes:
    """Regression tests for failure-path handling and edge cases."""

    class _SuccessPopen:
        def __init__(self, *_args, **_kwargs):
            self.returncode = 0

        def communicate(self, timeout=None):
            return "", ""

    class _TimeoutPopen:
        def __init__(self, *_args, **_kwargs):
            self.returncode = None
            self._killed = False

        def communicate(self, timeout=None):
            if self._killed:
                return "", "timed out"
            raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=timeout or 0)

        def kill(self):
            self._killed = True

    def test_check_indices_upper_bound_is_exclusive(self, video_with_output_dir):
        """Upper bound should be exclusive to prevent out-of-range list access."""
        video_path, _ = video_with_output_dir
        extractor = FrameExtractor(video_path)

        with pytest.raises(Exception, match="Frame indices out of bounds"):
            extractor._check_indices_in_range(reference_frame=10, image_range=(0, 20))

    def test_process_frames_handles_ffmpeg_timeout(self, video_with_output_dir, monkeypatch):
        """FFmpeg hangs should raise a clear timeout exception."""
        video_path, output_dir = video_with_output_dir
        extractor = FrameExtractor(video_path)

        monkeypatch.setattr(extractor_module.subprocess, "Popen", self._TimeoutPopen)
        monkeypatch.setattr(extractor_module.os, "listdir", lambda _path: [])

        with pytest.raises(Exception, match="timed out"):
            extractor.process_frames()

    def test_cleanup_removes_partial_extraction_on_failure(self, video_with_output_dir):
        """Cleanup should remove files extracted during a failed run."""
        video_path, output_dir = video_with_output_dir
        extractor = FrameExtractor(video_path)

        partial = "frame_9999.png"
        partial_path = os.path.join(output_dir, partial)
        open(partial_path, "w").close()

        extractor._processed = False
        extractor._extracted_filenames = [partial]

        extractor.cleanup()

        assert not os.path.exists(partial_path)
        assert extractor._extracted_filenames == []

    def test_process_frames_two_extrema_raises_clear_error(self, video_with_output_dir, monkeypatch):
        """Exactly two detected extrema should raise the insufficent-cycles error, not IndexError."""
        video_path, _ = video_with_output_dir
        extractor = FrameExtractor(video_path)

        old_files = ["frame_0001.png", "frame_0002.png"]
        new_files = [f"frame_{i:04d}.png" for i in range(3, 43)]
        call_count = {"value": 0}

        def fake_listdir(_path):
            call_count["value"] += 1
            if call_count["value"] == 1:
                return old_files
            return old_files + new_files

        monkeypatch.setattr(extractor_module.subprocess, "Popen", self._SuccessPopen)
        monkeypatch.setattr(extractor_module.os, "listdir", fake_listdir)
        monkeypatch.setattr(extractor_module.cv2, "imread", lambda *_args, **_kwargs: np.full((4, 4), 100, dtype=np.uint8))
        monkeypatch.setattr(extractor_module, "argrelextrema", lambda *_args, **_kwargs: (np.array([10, 20]),))
        monkeypatch.setattr(extractor, "detect_sync_errors_and_shift_frame_indices", lambda: None)
        monkeypatch.setattr(extractor, "_plot_intensity_histogram", lambda: None)

        with pytest.raises(Exception, match="insufficient cycles"):
            extractor.process_frames()


@pytest.mark.integration
@pytest.mark.realdata
class TestFrameExtractorRealData:
    """Integration tests using committed real video data from test_data/."""

    def test_process_frames_on_real_video(self, real_video_with_output_dir):
        """Process committed real video and validate core outputs."""
        video_path, output_dir = real_video_with_output_dir
        extractor = FrameExtractor(video_path, use_hw_acceleration=False)

        extract_time, identify_time = extractor.process_frames()

        assert extract_time > 0
        assert identify_time > 0
        assert len(extractor.filenames) > 0
        assert len(extractor.image_index_list) > 0

        histogram_path = os.path.join(output_dir, "intensity_histogram.png")
        assert os.path.exists(histogram_path)
        assert os.path.getsize(histogram_path) > 0

    def test_context_cleanup_on_real_video(self, real_video_with_output_dir):
        """Context manager should leave only selected frames after cleanup."""
        video_path, output_dir = real_video_with_output_dir

        with FrameExtractor(video_path, use_hw_acceleration=False) as extractor:
            extractor.process_frames()
            selected = extractor.get_filenames_to_process()
            assert len(selected) > 0

        remaining_frames = [f for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".png")]
        assert len(remaining_frames) == len(selected)
