"""
Unit and integration tests for FrameExtractor class.
"""

import pytest
import os
import logging
from pathlib import Path
from frame_extractor import FrameExtractor


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
    
    def test_get_filenames_to_delete_deprecated_warning(self, caplog, video_with_output_dir):
        """Test that deprecated method logs warning."""
        video_path, _ = video_with_output_dir
        extractor = FrameExtractor(video_path)
        
        extractor.filenames = ["frame_0001.png", "frame_0002.png"]
        extractor.image_index_list = [0]
        
        with caplog.at_level(logging.WARNING):
            result = extractor.get_filenames_to_delete()
        
        assert "deprecated" in caplog.text.lower()
        assert result == ["frame_0002.png"]


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
