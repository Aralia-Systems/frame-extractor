# Frame Extractor Testing Suite

Comprehensive test suite for the `frame_extractor` package.

## Running Tests

### Prerequisites
```bash
pip install pytest opencv-python numpy scipy
```

### Run All Tests
```bash
pytest testing/
```

### Run Specific Test Class
```bash
pytest testing/test_frame_extractor.py::TestFrameExtractorInitialization -v
```

### Run with Coverage
```bash
pip install pytest-cov
pytest testing/ --cov=frame_extractor --cov-report=html
```

### Run Verbose Output
```bash
pytest testing/ -v
```

### Run with Logging
```bash
pytest testing/ -v --log-cli-level=DEBUG
```

## Test Organization

### TestFrameExtractorInitialization
Tests for proper initialization of the FrameExtractor class:
- Video path storage
- Output folder setup
- Empty collection initialization
- Processed flag initialization

### TestFrameExtractorContextManager
Tests for context manager (`with` statement) support:
- `__enter__` returns self
- `__exit__` triggers cleanup
- Proper resource management

### TestFrameExtractorCleanup
Tests for the cleanup functionality:
- Cleanup before processing (no-op)
- Deletion of unselected files
- Handling of missing files
- All files selected scenario

### TestFrameExtractorGetters
Tests for the getter methods:
- Error conditions before processing
- Correct list/filename returns
- Deprecated method warnings

### TestFrameExtractorIntegration
Integration tests with actual video processing:
- Frame extraction and file creation
- Frame identification and index calculation
- Context manager with actual processing
- Requires FFmpeg and VideoWriter support

### TestFrameExtractorEdgeCases
Edge case and error condition tests:
- Nonexistent video files
- Empty collections
- Invalid states

## Test Fixtures

### temp_video_dir
Creates a temporary directory for test files.

### sample_video_path
Generates a test video with 30 frames showing intensity changes over 2 seconds.

### output_dir
Creates an output directory for frame extraction.

### video_with_output_dir
Combines the above to create a complete test scenario.

## Notes

- Integration tests are skipped on non-Windows systems (adjust as needed for your CI/CD)
- FFmpeg must be installed for integration tests
- OpenCV's VideoWriter requires proper codec support
- Tests use temporary directories; cleanup is automatic

## Continuous Integration

For CI/CD pipelines, consider:
1. Installing FFmpeg: `apt-get install ffmpeg` (Linux) or `brew install ffmpeg` (Mac)
2. Using `pytest --tb=short` for compact output
3. Skipping integration tests in environments without FFmpeg
4. Running coverage checks: `--cov` flag
