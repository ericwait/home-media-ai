"""
Quality evaluation engine for images and videos.

This module provides the main QualityEvaluator class that orchestrates
quality assessment for both images and videos using computer vision techniques.

Classes:
    QualityEvaluator: Main class for quality assessment operations
    
Example:
    >>> from home_media_ai.quality import QualityEvaluator
    >>> evaluator = QualityEvaluator()
    >>> metrics = evaluator.evaluate_image('/path/to/image.jpg')
    >>> print(f"Image quality: {metrics.overall_score}/100")
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Union, Optional, List, Tuple
import logging
from PIL import Image, ImageStat
from skimage import filters, measure, feature
from skimage.restoration import estimate_sigma

from ..utils import get_file_info, is_image_file, is_video_file
from ..config import get_config
from .metrics import ImageQualityMetrics, VideoQualityMetrics

logger = logging.getLogger(__name__)


class QualityEvaluator:
    """Main quality evaluation engine for images and videos.
    
    This class provides methods to assess the quality of images and videos
    using various computer vision and signal processing techniques.
    
    Attributes:
        config: Configuration settings for quality assessment
        
    Example:
        >>> evaluator = QualityEvaluator()
        >>> image_metrics = evaluator.evaluate_image('/path/to/photo.jpg')
        >>> video_metrics = evaluator.evaluate_video('/path/to/video.mp4')
    """
    
    def __init__(self, config=None):
        """Initialize the quality evaluator.
        
        Args:
            config: Optional configuration object (uses global config if None)
        """
        self.config = config or get_config()
        logger.info("Quality evaluator initialized")
    
    def evaluate_image(self, image_path: Union[str, Path]) -> ImageQualityMetrics:
        """Evaluate the quality of an image file.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            ImageQualityMetrics containing all quality scores
            
        Raises:
            FileNotFoundError: If image file doesn't exist
            ValueError: If file is not a supported image format
            
        Example:
            >>> evaluator = QualityEvaluator()
            >>> metrics = evaluator.evaluate_image('/path/to/photo.jpg')
            >>> if metrics.overall_score > 80:
            ...     print("High quality image")
        """
        image_path = Path(image_path)
        
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        if not is_image_file(image_path):
            raise ValueError(f"File is not a supported image format: {image_path}")
        
        logger.debug(f"Evaluating image quality: {image_path}")
        
        try:
            # Load image using OpenCV for analysis
            image_cv = cv2.imread(str(image_path))
            if image_cv is None:
                raise ValueError(f"Could not load image: {image_path}")
            
            # Also load with PIL for additional analysis
            image_pil = Image.open(image_path)
            
            # Calculate quality metrics
            metrics = ImageQualityMetrics(
                blur_score=self._calculate_blur_score(image_cv),
                brightness_score=self._calculate_brightness_score(image_cv),
                contrast_score=self._calculate_contrast_score(image_cv),
                noise_score=self._calculate_noise_score(image_cv),
                sharpness_score=self._calculate_sharpness_score(image_cv),
                saturation_score=self._calculate_saturation_score(image_cv),
                exposure_score=self._calculate_exposure_score(image_cv),
            )
            
            # Calculate face quality if enabled
            if self.config.content.enable_face_detection:
                try:
                    face_score = self._calculate_face_quality_score(image_cv)
                    metrics.face_quality_score = face_score
                except Exception as e:
                    logger.debug(f"Face quality assessment failed: {e}")
            
            logger.debug(f"Image quality evaluation complete: {metrics.overall_score:.1f}/100")
            return metrics
            
        except Exception as e:
            logger.error(f"Error evaluating image quality for {image_path}: {e}")
            # Return default metrics on error
            return ImageQualityMetrics()
    
    def evaluate_video(self, video_path: Union[str, Path]) -> VideoQualityMetrics:
        """Evaluate the quality of a video file.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            VideoQualityMetrics containing all quality scores
            
        Raises:
            FileNotFoundError: If video file doesn't exist
            ValueError: If file is not a supported video format
            
        Example:
            >>> evaluator = QualityEvaluator()
            >>> metrics = evaluator.evaluate_video('/path/to/video.mp4')
            >>> if metrics.overall_score > 70:
            ...     print("Good quality video")
        """
        video_path = Path(video_path)
        
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        if not is_video_file(video_path):
            raise ValueError(f"File is not a supported video format: {video_path}")
        
        logger.debug(f"Evaluating video quality: {video_path}")
        
        try:
            # Open video with OpenCV
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise ValueError(f"Could not open video: {video_path}")
            
            # Get video properties
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = total_frames / fps if fps > 0 else 0
            
            # Sample frames for quality assessment
            frame_indices = self._get_sample_frame_indices(
                total_frames, 
                self.config.quality.video_sample_frames
            )
            
            frame_qualities = []
            motion_blur_scores = []
            previous_frame = None
            
            for frame_idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                
                if ret:
                    # Evaluate frame quality
                    frame_metrics = self._evaluate_video_frame(frame)
                    frame_qualities.append(frame_metrics.overall_score)
                    
                    # Calculate motion blur if we have a previous frame
                    if previous_frame is not None:
                        motion_score = self._calculate_motion_blur_score(previous_frame, frame)
                        motion_blur_scores.append(motion_score)
                    
                    previous_frame = frame.copy()
            
            cap.release()
            
            # Calculate overall metrics
            avg_frame_quality = np.mean(frame_qualities) if frame_qualities else 0.0
            motion_blur_score = np.mean(motion_blur_scores) if motion_blur_scores else 0.0
            stability_score = self._calculate_stability_score(motion_blur_scores)
            compression_score = self._calculate_compression_score(video_path)
            
            metrics = VideoQualityMetrics(
                avg_frame_quality=avg_frame_quality,
                motion_blur_score=motion_blur_score,
                stability_score=stability_score,
                compression_score=compression_score,
                frame_consistency_score=100.0 - (np.std(frame_qualities) if frame_qualities else 0.0),
                duration_seconds=duration,
                frame_rate=fps,
                resolution_width=width,
                resolution_height=height,
            )
            
            logger.debug(f"Video quality evaluation complete: {metrics.overall_score:.1f}/100")
            return metrics
            
        except Exception as e:
            logger.error(f"Error evaluating video quality for {video_path}: {e}")
            return VideoQualityMetrics()
    
    def _calculate_blur_score(self, image: np.ndarray) -> float:
        """Calculate blur score using Laplacian variance.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            Blur score (0-100, higher is less blurry)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        # Normalize to 0-100 scale (adjust threshold based on config)
        threshold = self.config.quality.blur_threshold
        score = min(100.0, (laplacian_var / threshold) * 100.0)
        return score
    
    def _calculate_brightness_score(self, image: np.ndarray) -> float:
        """Calculate brightness quality score.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            Brightness score (0-100, optimal brightness gets higher score)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mean_brightness = np.mean(gray)
        
        # Optimal brightness range from config
        min_bright = self.config.quality.brightness_min
        max_bright = self.config.quality.brightness_max
        optimal = (min_bright + max_bright) / 2
        
        # Score based on distance from optimal
        if min_bright <= mean_brightness <= max_bright:
            # Within acceptable range
            distance_from_optimal = abs(mean_brightness - optimal)
            max_distance = (max_bright - min_bright) / 2
            score = 100.0 - (distance_from_optimal / max_distance) * 50.0
        else:
            # Outside acceptable range
            if mean_brightness < min_bright:
                score = (mean_brightness / min_bright) * 50.0
            else:
                score = ((255 - mean_brightness) / (255 - max_bright)) * 50.0
        
        return max(0.0, min(100.0, score))
    
    def _calculate_contrast_score(self, image: np.ndarray) -> float:
        """Calculate contrast quality score.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            Contrast score (0-100, higher contrast gets higher score)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        contrast = gray.std()
        
        # Normalize contrast (typical range 0-100)
        score = min(100.0, (contrast / 50.0) * 100.0)
        
        # Apply minimum threshold from config
        min_contrast = self.config.quality.contrast_min * 100
        if score < min_contrast:
            score *= 0.5  # Penalize low contrast
        
        return score
    
    def _calculate_noise_score(self, image: np.ndarray) -> float:
        """Calculate noise quality score.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            Noise score (0-100, lower noise gets higher score)
        """
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            # Estimate noise using scikit-image
            noise_sigma = estimate_sigma(gray, multichannel=False)
            
            # Normalize noise score (typical sigma range 0-20)
            threshold = self.config.quality.noise_threshold * 20
            score = max(0.0, 100.0 - (noise_sigma / threshold) * 100.0)
            return min(100.0, score)
            
        except Exception:
            # Fallback method using standard deviation of Laplacian
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            noise_estimate = laplacian.std()
            score = max(0.0, 100.0 - noise_estimate)
            return min(100.0, score)
    
    def _calculate_sharpness_score(self, image: np.ndarray) -> float:
        """Calculate sharpness quality score.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            Sharpness score (0-100, higher sharpness gets higher score)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Use gradient magnitude for sharpness
        grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        sharpness = np.sqrt(grad_x**2 + grad_y**2).mean()
        
        # Normalize to 0-100 scale
        score = min(100.0, (sharpness / 50.0) * 100.0)
        return score
    
    def _calculate_saturation_score(self, image: np.ndarray) -> float:
        """Calculate color saturation score.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            Saturation score (0-100, optimal saturation gets higher score)
        """
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1].mean()
        
        # Optimal saturation range (not too dull, not oversaturated)
        if 80 <= saturation <= 180:
            score = 100.0
        elif saturation < 80:
            score = (saturation / 80.0) * 80.0
        else:
            score = ((255 - saturation) / (255 - 180)) * 80.0
        
        return max(0.0, min(100.0, score))
    
    def _calculate_exposure_score(self, image: np.ndarray) -> float:
        """Calculate exposure quality score.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            Exposure score (0-100, proper exposure gets higher score)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Check for over/under exposure
        total_pixels = gray.size
        overexposed = np.sum(gray > 245) / total_pixels
        underexposed = np.sum(gray < 10) / total_pixels
        
        # Penalize over/under exposure
        exposure_penalty = (overexposed + underexposed) * 100.0
        score = max(0.0, 100.0 - exposure_penalty)
        
        return score
    
    def _calculate_face_quality_score(self, image: np.ndarray) -> Optional[float]:
        """Calculate face quality score if faces are detected.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            Face quality score (0-100) or None if no faces detected
        """
        # This is a simplified implementation
        # In a full implementation, you might use face_recognition library
        # or other face detection/quality assessment tools
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Use OpenCV's built-in face cascade
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        if len(faces) == 0:
            return None
        
        # Calculate quality based on face size and sharpness
        face_scores = []
        for (x, y, w, h) in faces:
            face_region = gray[y:y+h, x:x+w]
            
            # Face size score (larger faces generally better)
            size_score = min(100.0, (w * h) / 10000.0 * 100.0)
            
            # Face sharpness score
            face_sharpness = cv2.Laplacian(face_region, cv2.CV_64F).var()
            sharpness_score = min(100.0, face_sharpness / 50.0)
            
            face_scores.append((size_score + sharpness_score) / 2.0)
        
        return np.mean(face_scores) if face_scores else None
    
    def _evaluate_video_frame(self, frame: np.ndarray) -> ImageQualityMetrics:
        """Evaluate quality of a single video frame.
        
        Args:
            frame: Video frame as numpy array
            
        Returns:
            ImageQualityMetrics for the frame
        """
        return ImageQualityMetrics(
            blur_score=self._calculate_blur_score(frame),
            brightness_score=self._calculate_brightness_score(frame),
            contrast_score=self._calculate_contrast_score(frame),
            noise_score=self._calculate_noise_score(frame),
            sharpness_score=self._calculate_sharpness_score(frame),
        )
    
    def _calculate_motion_blur_score(self, prev_frame: np.ndarray, curr_frame: np.ndarray) -> float:
        """Calculate motion blur score between two frames.
        
        Args:
            prev_frame: Previous frame
            curr_frame: Current frame
            
        Returns:
            Motion blur score (0-100, higher is less motion blur)
        """
        # Convert to grayscale
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)
        
        # Calculate frame difference
        diff = cv2.absdiff(prev_gray, curr_gray)
        motion_magnitude = np.mean(diff)
        
        # Convert to quality score (less motion = higher score)
        score = max(0.0, 100.0 - motion_magnitude)
        return score
    
    def _calculate_stability_score(self, motion_scores: List[float]) -> float:
        """Calculate video stability score from motion blur scores.
        
        Args:
            motion_scores: List of motion blur scores
            
        Returns:
            Stability score (0-100, higher is more stable)
        """
        if not motion_scores:
            return 0.0
        
        # Stability is inverse of motion variance
        motion_variance = np.var(motion_scores)
        score = max(0.0, 100.0 - motion_variance)
        return score
    
    def _calculate_compression_score(self, video_path: Path) -> float:
        """Calculate compression quality score based on file size and duration.
        
        Args:
            video_path: Path to video file
            
        Returns:
            Compression score (0-100, higher is better quality)
        """
        try:
            file_info = get_file_info(video_path)
            file_size_mb = file_info['size_bytes'] / (1024 * 1024)
            
            # Estimate bitrate (rough approximation)
            # This is a simplified method - proper implementation would use ffprobe
            cap = cv2.VideoCapture(str(video_path))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration = frame_count / fps if fps > 0 else 1
            cap.release()
            
            bitrate_mbps = (file_size_mb * 8) / duration if duration > 0 else 0
            
            # Score based on bitrate (higher generally better, but with diminishing returns)
            if bitrate_mbps > 10:
                score = 100.0
            elif bitrate_mbps > 5:
                score = 80.0 + (bitrate_mbps - 5) * 4.0
            elif bitrate_mbps > 2:
                score = 60.0 + (bitrate_mbps - 2) * 6.67
            else:
                score = bitrate_mbps * 30.0
            
            return min(100.0, score)
            
        except Exception:
            return 50.0  # Default score if calculation fails
    
    def _get_sample_frame_indices(self, total_frames: int, sample_count: int) -> List[int]:
        """Get evenly distributed frame indices for sampling.
        
        Args:
            total_frames: Total number of frames in video
            sample_count: Number of frames to sample
            
        Returns:
            List of frame indices to sample
        """
        if total_frames <= sample_count:
            return list(range(total_frames))
        
        # Evenly distribute samples across the video
        step = total_frames // sample_count
        indices = [i * step for i in range(sample_count)]
        
        # Make sure we don't exceed total frames
        return [min(idx, total_frames - 1) for idx in indices]