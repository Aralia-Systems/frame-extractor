class FrameExtractor:
    """
    A class for processing frames from a video using FFmpeg and OpenCV.

    Args:
        input_video_path (str): The path to the input video file.
        output_folder (str, optional): The folder where processed frames will be saved. Default is './output_frames'.

    Attributes:
        input_video_path (str): The path to the input video file.
        output_folder (str): The folder where processed frames will be saved.
        image_index_list (list): A list to store image indices used for further processing.

    Methods:
        process_frames(output_height=1920, output_width=1080):
            Process frames from the input video and save them as PNG images in the output folder.
            Optionally, specify the output image dimensions (height and width).

        Note: After processing frames, you can access the `image_index_list` attribute to retrieve image indices
        used for further processing.

    Example:
        processor = FrameProcessor('input_video.mp4', output_folder='./output_frames')
        extract_time, identify_time = processor.process_frames(output_height=720, output_width=1280)
        print(f"Extraction time: {extract_time} seconds")
        print(f"Identification time: {identify_time} seconds")
        print(f"Image indices for further processing: {processor.image_index_list}")

    """

    def __init__(self, input_video_filepath):
        self.input_video_path = input_video_filepath
        self.image_folder_path = os.path.dirname(input_video_filepath)
        self.image_index_list = []
        self.width = None
        self.height = None
        self.filenames = []
        self.mean_intensity = []

    def process_frames(self, output_height=1920, output_width=1080):
        """
        Process frames from the input video and save them as PNG images.

        Args:
            output_height (int, optional): The height of the output images. Default is 1920 pixels.
            output_width (int, optional): The width of the output images. Default is 1080 pixels.

        Returns:
            float: The time taken for frame extraction in seconds.
            float: The time taken for frame identification in seconds.

        Note:
            After processing frames, you can access the `image_index_list` attribute to retrieve image indices
            used for further processing.
        """
        # identify algorithm runs faster with small images
        # scale_npp=60:-1 will output a 60px width image and maintain height aspect

        # Not needed?

        # cap = cv2.VideoCapture(self.input_video_path)

        # if not cap.isOpened():
        #     raise Exception("could not open video file")
        # else:
        #     self.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        #     self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        #     print(f'height: {self.height}')
        #     print(f'width: {self.width}')

        # cap.release()

        # http://underpop.online.fr/f/ffmpeg/help/scale_005fnpp.htm.gz
        # interp_algo
        # - super
        # - lanczos

        ffmpeg_cmd = [
            'ffmpeg',
            '-hwaccel', 'nvdec',
            '-i', self.input_video_path,
            '-vsync', '0',
            os.path.join(self.image_folder_path, 'frame_%04d.png')]        


        # ffmpeg_cmd = [
        #     'ffmpeg',
        #     '-hwaccel', 'nvdec',
        #     '-hwaccel_device', '0',
        #     '-hwaccel_output_format', 'cuda',
        #     '-noautorotate',
        #     '-i', self.input_video_path,
        #     '-r', '30',
        #     '-map', '0:0',
        #     '-map', '0:1?',
        #     '-vf', f'scale_npp={self.height}:{self.width}:interp_algo=lanczos,hwdownload,format=nv12,transpose=1',
        #     '-c:v:0', 'png',
        #     '-f', 'image2',
        #     os.path.join(self.image_folder_path, 'frame_%04d.png')
        # ]

        # Measure the time it takes to run the subprocess
        start_time_extract = time.time()
        process = subprocess.Popen(ffmpeg_cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        stdout, stderr = process.communicate()
        print(stdout)
        print(stderr)
        exit_code = process.wait()    
        if exit_code != 0:
            raise Exception(f'process failed')
        end_time_extract = time.time()

        # Initialize variables
        difference = []
        frame_n1 = None
        # some area for improvement here if the first cycle is ignored
        # could start identification later in the frame sequence
        start_range = 0
        num_of_images = 0
    
        # Measure the time it takes to process the images
        start_time_identify = time.time()

        # print(sorted(os.listdir(self.image_folder_path)))
        
        # Iterate through the images in the folder
        # issue with using index because there are other files in the folder
        # temporarily disabled stuff using idx
        for idx, filename in enumerate(sorted(os.listdir(self.image_folder_path))):
            if idx > 100:
                raise Exception("too many images something went wrong with frame extraction")
            if filename.endswith('.png') and filename.startswith("frame_"):
                image_path = os.path.join(self.image_folder_path, filename)
                frame = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
                # we could skip the first x may give slight speed increase
                if frame_n1 is not None:
                    self.mean_intensity.append(np.mean(frame))
                    diff = np.mean(abs(frame_n1 - frame))
                    difference.append(diff)
                else:
                    self.mean_intensity.append(0)

                frame_n1 = frame
                num_of_images += 1

                self.filenames.append(filename)  # Store filenames
            else:
                continue

            print(num_of_images)

        process_range = (start_range, num_of_images)

        # Calculate rolled_mean and maximal_diff2
        rolled_mean = np.roll(self.mean_intensity, 2)
        diff_2 = self.mean_intensity - rolled_mean
        maximal_diff2 = np.asarray(argrelextrema(diff_2, np.greater, order=12))
        maximal_diff2 = np.concatenate(maximal_diff2)
        sorted_diffs = maximal_diff2[np.argsort(-1 * diff_2[maximal_diff2])]
        print(maximal_diff2)

        # Measure the time it takes to process the images
        end_time_identify = time.time()

        # no longer using argsort for the diffs
        # there are typically 5 cycles in the 2 second video
        # EV converges at the second cycle so best sequence to extract is the second or third
        if len(maximal_diff2) >= 2:
            current_value = maximal_diff2[2]
        # if this is the last sequence it's possible the indexs may be invalid
        elif len(maximal_diff2 == 1):
            current_value = maximal_diff2[0]
        else:
            raise Exception("failed to find sequence start frame")

        # Calculate and print the times
        extract_time = end_time_extract - start_time_extract
        identify_time = end_time_identify - start_time_identify

        self.image_index_list = self._check_indices_in_range(current_value, process_range)

        self.detect_sync_errors_and_shift_frame_indices()
        
        return extract_time, identify_time
    
    # calculating image range could be improved 
    def _check_indices_in_range(self, reference_frame, image_range):
        index_mask_list = [-3, 0, 3, 6, 9, 12]
        # index_mask_list = [-4, 0, 4, 8, 12, 16]
        masked_list = [x + reference_frame for x in index_mask_list]
        all_in_range = all(start_idx >= image_range[0] and start_idx <= image_range[1] for start_idx in masked_list)

        if all_in_range:
            return masked_list
        else:
            raise Exception("image index out of bounds")

    # adding a getter so calling code is explicit

    def detect_sync_errors_and_shift_frame_indices(self):
        min_index = min(self.image_index_list)
        max_index = self.image_index_list[2]
        sequence_to_process = [self.filenames[x] for x in range(min_index, max_index)]
        # filename = filenames_to_process[1]
        # abs_path = os.path.join(self.image_folder_path, filename)
        img_n1 = None
        mean_diff_list = []
        for i, image in enumerate(sequence_to_process):
            if i == 0:
                img_n1 = cv2.imread(os.path.join(self.image_folder_path, image))
                continue
            img = cv2.imread(os.path.join(self.image_folder_path, image))
            mean_diff = np.mean((img - img_n1))
            img_n1 = img
            mean_diff_list.append(mean_diff)

        print(mean_diff_list)

        # Check if index 1 is greater than index 0
        if mean_diff_list[1] > mean_diff_list[0]:
        # Count how many items from the right (excluding the first two) are less than the item at index 1
            count_less_than_index_1 = sum(value < mean_diff_list[1] for value in mean_diff_list[2:])

        # There should only be one such item
            if count_less_than_index_1 > 1:
                print("reindexing frames")
                # self.image_index_list = [x + 1 for x in self.image_index_list]
            else:
                print("frame indexes unaltered")
        else:
            print("possible frame sync issue detected")
            

    def get_image_index_list(self):
        if not self.image_index_list:
            raise Exception("image_index_list is None")
        return self.image_index_list

    def get_filenames_to_process(self) -> list:
        if not self.image_index_list:
            raise Exception("image_index_list is None")
        if not self.filenames:
            raise Exception("filenames is None")
        filenames_to_process = [self.filenames[x] for x in self.image_index_list]
        return filenames_to_process
    
    def get_filenames_to_delete(self) -> list:
        if not self.image_index_list:
            raise Exception("image_index_list is None")
        if not self.filenames:
            raise Exception("filenames is None")
        filenames_to_delete = [self.filenames[x] for x in range(len(self.filenames)) if x not in self.image_index_list]
        return filenames_to_delete
