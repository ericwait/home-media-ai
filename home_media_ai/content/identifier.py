"""
Content identification engine for images and videos.

This module provides the main ContentIdentifier class that performs
face detection, object detection, scene classification, and text extraction
from images and videos.

Classes:
    ContentIdentifier: Main class for content identification operations
    
Example:
    >>> from home_media_ai.content import ContentIdentifier
    >>> identifier = ContentIdentifier()
    >>> result = identifier.analyze_image('/path/to/image.jpg')
    >>> print(f"Found {result.face_count} faces and {result.object_count} objects")
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Union, List, Tuple, Optional
import logging
import time

try:
    from sklearn.cluster import KMeans
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logging.warning("scikit-learn not available, some features disabled")

from ..utils import get_file_info, is_image_file, is_video_file
from ..config import get_config
from .detection import DetectionResult, FaceInfo, ObjectInfo

logger = logging.getLogger(__name__)


class ContentIdentifier:
    """Main content identification engine for images and videos.
    
    This class provides methods to identify and analyze content in images
    and videos, including faces, objects, scenes, and text.
    
    Attributes:
        config: Configuration settings for content identification
        face_cascade: OpenCV face detection cascade
        
    Example:
        >>> identifier = ContentIdentifier()
        >>> result = identifier.analyze_image('/path/to/photo.jpg')
        >>> for face in result.faces:
        ...     print(f"Face at {face.bbox} with confidence {face.confidence}")
    """
    
    def __init__(self, config=None):
        """Initialize the content identifier.
        
        Args:
            config: Optional configuration object (uses global config if None)
        """
        self.config = config or get_config()
        self.face_cascade = None
        self._load_detection_models()
        logger.info("Content identifier initialized")
    
    def analyze_image(self, image_path: Union[str, Path]) -> DetectionResult:
        """Analyze content in an image file.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            DetectionResult containing all identified content
            
        Raises:
            FileNotFoundError: If image file doesn't exist
            ValueError: If file is not a supported image format
            
        Example:
            >>> identifier = ContentIdentifier()
            >>> result = identifier.analyze_image('/path/to/photo.jpg')
            >>> if result.has_faces:
            ...     print(f"Found {result.face_count} faces")
        """
        image_path = Path(image_path)
        
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        if not is_image_file(image_path):
            raise ValueError(f"File is not a supported image format: {image_path}")
        
        logger.debug(f"Analyzing image content: {image_path}")
        start_time = time.time()
        
        try:
            # Load image
            image = cv2.imread(str(image_path))
            if image is None:
                raise ValueError(f"Could not load image: {image_path}")
            
            # Initialize result container
            result = DetectionResult()
            
            # Detect faces if enabled
            if self.config.content.enable_face_detection:
                result.faces = self._detect_faces(image)
            
            # Detect objects if enabled
            if self.config.content.enable_object_detection:
                result.objects = self._detect_objects(image)
            
            # Extract text if enabled
            if self.config.content.enable_text_extraction:
                result.text_content = self._extract_text(image)
            
            # Classify scene if enabled
            if self.config.content.enable_scene_classification:
                result.scene_labels = self._classify_scene(image)
            
            # Extract dominant colors
            result.dominant_colors = self._extract_dominant_colors(image)
            
            # Generate tags based on detected content
            result.tags = self._generate_tags(result)
            
            # Record processing time
            result.processing_time = time.time() - start_time
            
            logger.debug(f"Image analysis complete: {result.face_count} faces, "
                        f"{result.object_count} objects, {result.processing_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing image content for {image_path}: {e}")
            # Return empty result on error
            result = DetectionResult()
            result.processing_time = time.time() - start_time
            return result
    
    def analyze_video(self, video_path: Union[str, Path], sample_frames: int = 5) -> DetectionResult:
        """Analyze content in a video file by sampling frames.
        
        Args:
            video_path: Path to the video file
            sample_frames: Number of frames to sample for analysis
            
        Returns:
            DetectionResult containing aggregated content from sampled frames
            
        Raises:
            FileNotFoundError: If video file doesn't exist
            ValueError: If file is not a supported video format
            
        Example:
            >>> identifier = ContentIdentifier()
            >>> result = identifier.analyze_video('/path/to/video.mp4')
            >>> print(f"Video contains: {', '.join(result.get_object_classes())}")
        """
        video_path = Path(video_path)
        
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        if not is_video_file(video_path):
            raise ValueError(f"File is not a supported video format: {video_path}")
        
        logger.debug(f"Analyzing video content: {video_path}")
        start_time = time.time()
        
        try:
            # Open video
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise ValueError(f"Could not open video: {video_path}")
            
            # Get video properties
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            frame_indices = self._get_sample_frame_indices(total_frames, sample_frames)
            
            # Aggregate results from all frames
            all_faces = []
            all_objects = []
            all_scene_labels = []
            all_text = []
            all_colors = []
            
            for frame_idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                
                if ret:
                    # Analyze this frame
                    frame_result = self._analyze_frame(frame)
                    
                    # Aggregate results
                    all_faces.extend(frame_result.faces)
                    all_objects.extend(frame_result.objects)
                    all_scene_labels.extend(frame_result.scene_labels)
                    if frame_result.text_content:
                        all_text.append(frame_result.text_content)
                    all_colors.extend(frame_result.dominant_colors)
            
            cap.release()
            
            # Create aggregated result
            result = DetectionResult(
                faces=self._deduplicate_faces(all_faces),
                objects=self._deduplicate_objects(all_objects),
                scene_labels=self._aggregate_scene_labels(all_scene_labels),
                text_content=' '.join(all_text) if all_text else None,
                dominant_colors=self._aggregate_colors(all_colors),
                processing_time=time.time() - start_time
            )
            
            # Generate tags
            result.tags = self._generate_tags(result)
            
            logger.debug(f"Video analysis complete: {result.face_count} faces, "
                        f"{result.object_count} objects, {result.processing_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing video content for {video_path}: {e}")
            result = DetectionResult()
            result.processing_time = time.time() - start_time
            return result
    
    def _load_detection_models(self):
        """Load detection models and cascades."""
        try:
            # Load face detection cascade
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
            
            if self.face_cascade.empty():
                logger.warning("Could not load face detection cascade")
                self.face_cascade = None
            else:
                logger.debug("Face detection cascade loaded successfully")
                
        except Exception as e:
            logger.warning(f"Error loading detection models: {e}")
    
    def _detect_faces(self, image: np.ndarray) -> List[FaceInfo]:
        """Detect faces in an image.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            List of detected faces
        """
        if self.face_cascade is None:
            return []
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = self.face_cascade.detectMultiScale(
            gray, 
            scaleFactor=1.1, 
            minNeighbors=5,
            minSize=(30, 30)
        )
        
        face_list = []
        max_faces = self.config.content.max_faces_per_image
        
        for (x, y, w, h) in faces[:max_faces]:
            # Calculate confidence (simplified - in real implementation you might use a more sophisticated method)
            face_region = gray[y:y+h, x:x+w]
            confidence = self._calculate_face_confidence(face_region)
            
            # Filter by confidence threshold
            if confidence >= self.config.content.face_confidence_threshold:
                face_info = FaceInfo(
                    bbox=(x, y, w, h),
                    confidence=confidence,
                    quality_score=self._assess_face_quality(face_region)
                )
                face_list.append(face_info)
        
        return face_list
    
    def _detect_objects(self, image: np.ndarray) -> List[ObjectInfo]:
        """Detect objects in an image.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            List of detected objects
        """
        # This is a simplified implementation
        # In a full implementation, you would use models like YOLO, SSD, or RCNN
        
        # For now, we'll implement a basic edge-based object detection
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Find edges
        edges = cv2.Canny(gray, 50, 150)
        
        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        objects = []
        min_area = 1000  # Minimum object area
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > min_area:
                # Get bounding box
                x, y, w, h = cv2.boundingRect(contour)
                
                # Simple object classification based on shape
                aspect_ratio = w / h
                object_class = self._classify_simple_object(aspect_ratio, area)
                
                confidence = min(1.0, area / 10000.0)  # Simplified confidence
                
                if confidence >= self.config.content.object_confidence_threshold:
                    obj_info = ObjectInfo(
                        bbox=(x, y, w, h),
                        confidence=confidence,
                        class_name=object_class,
                        class_id=hash(object_class) % 1000
                    )
                    objects.append(obj_info)
        
        return objects
    
    def _extract_text(self, image: np.ndarray) -> Optional[str]:
        """Extract text from an image using OCR.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            Extracted text or None if no text found
        """
        # This would typically use pytesseract or other OCR libraries
        # For now, return None as OCR is disabled by default
        logger.debug("Text extraction not implemented (requires pytesseract)")
        return None
    
    def _classify_scene(self, image: np.ndarray) -> List[Tuple[str, float]]:
        """Classify the scene in an image.
        
        Args:
            image: Input image as numpy array
            
        Returns:
            List of (scene_label, confidence) tuples
        """
        # This is a simplified scene classification
        # In practice, you would use pre-trained models like ResNet, VGG, etc.
        
        # Analyze color distribution for basic scene classification
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        
        # Calculate color statistics
        h_mean = np.mean(hsv[:, :, 0])
        s_mean = np.mean(hsv[:, :, 1])
        v_mean = np.mean(hsv[:, :, 2])
        
        scenes = []
        
        # Simple heuristics for scene classification
        if v_mean > 200:
            scenes.append(('bright', 0.8))
        elif v_mean < 50:
            scenes.append(('dark', 0.8))
        
        if s_mean < 50:
            scenes.append(('indoor', 0.6))
        else:
            scenes.append(('outdoor', 0.6))
        
        # Green dominance suggests nature/outdoor
        if 40 <= h_mean <= 80 and s_mean > 100:
            scenes.append(('nature', 0.7))
        
        # Blue dominance suggests sky/water
        if 100 <= h_mean <= 130 and s_mean > 80:
            scenes.append(('sky_water', 0.7))
        
        return scenes
    
    def _extract_dominant_colors(self, image: np.ndarray, k: int = 5) -> List[Tuple[int, int, int]]:
        """Extract dominant colors from an image.
        
        Args:
            image: Input image as numpy array
            k: Number of dominant colors to extract
            
        Returns:
            List of (R, G, B) tuples for dominant colors
        """
        if not SKLEARN_AVAILABLE:
            # Fallback: return average color
            mean_color = np.mean(image.reshape(-1, 3), axis=0)
            return [(int(mean_color[2]), int(mean_color[1]), int(mean_color[0]))]  # BGR to RGB
        
        try:
            # Reshape image to be a list of pixels
            pixels = image.reshape(-1, 3)
            
            # Sample pixels for efficiency
            if len(pixels) > 10000:
                indices = np.random.choice(len(pixels), 10000, replace=False)
                pixels = pixels[indices]
            
            # Apply k-means clustering
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            kmeans.fit(pixels)
            
            # Get cluster centers (dominant colors) and convert BGR to RGB
            colors = []
            for color in kmeans.cluster_centers_:
                rgb = (int(color[2]), int(color[1]), int(color[0]))  # BGR to RGB
                colors.append(rgb)
            
            return colors
            
        except Exception as e:
            logger.debug(f"Error extracting dominant colors: {e}")
            # Fallback: return average color
            mean_color = np.mean(image.reshape(-1, 3), axis=0)
            return [(int(mean_color[2]), int(mean_color[1]), int(mean_color[0]))]
    
    def _generate_tags(self, result: DetectionResult) -> List[str]:
        """Generate descriptive tags based on detection results.
        
        Args:
            result: Detection result to generate tags from
            
        Returns:
            List of descriptive tags
        """
        tags = []
        
        # Face-based tags
        if result.has_faces:
            if result.face_count == 1:
                tags.append('portrait')
            elif result.face_count <= 3:
                tags.append('small_group')
            else:
                tags.append('large_group')
            
            tags.append(f'{result.face_count}_people')
        
        # Object-based tags
        if result.has_objects:
            object_classes = result.get_object_classes()
            tags.extend(object_classes)
        
        # Scene-based tags
        scene_predictions = result.get_scene_predictions(threshold=0.6)
        tags.extend(scene_predictions)
        
        # Text-based tags
        if result.has_text:
            tags.append('contains_text')
        
        # Color-based tags
        if result.dominant_colors:
            color_tags = self._generate_color_tags(result.dominant_colors)
            tags.extend(color_tags)
        
        return list(set(tags))  # Remove duplicates
    
    def _calculate_face_confidence(self, face_region: np.ndarray) -> float:
        """Calculate confidence score for a detected face.
        
        Args:
            face_region: Face region as grayscale numpy array
            
        Returns:
            Confidence score (0.0-1.0)
        """
        if face_region.size == 0:
            return 0.0
        
        # Simple confidence based on face size and contrast
        area = face_region.shape[0] * face_region.shape[1]
        contrast = face_region.std()
        
        # Larger faces and higher contrast generally indicate better detections
        size_score = min(1.0, area / 10000.0)
        contrast_score = min(1.0, contrast / 50.0)
        
        return (size_score + contrast_score) / 2.0
    
    def _assess_face_quality(self, face_region: np.ndarray) -> float:
        """Assess the quality of a detected face.
        
        Args:
            face_region: Face region as grayscale numpy array
            
        Returns:
            Quality score (0.0-1.0)
        """
        if face_region.size == 0:
            return 0.0
        
        # Simple quality assessment based on sharpness and size
        laplacian_var = cv2.Laplacian(face_region, cv2.CV_64F).var()
        sharpness_score = min(1.0, laplacian_var / 100.0)
        
        # Size score (larger faces generally better quality)
        area = face_region.shape[0] * face_region.shape[1]
        size_score = min(1.0, area / 5000.0)
        
        return (sharpness_score + size_score) / 2.0
    
    def _classify_simple_object(self, aspect_ratio: float, area: float) -> str:
        """Simple object classification based on shape properties.
        
        Args:
            aspect_ratio: Width/height ratio
            area: Object area in pixels
            
        Returns:
            Object class name
        """
        # Very simple classification based on shape
        if 0.8 <= aspect_ratio <= 1.2:
            if area > 50000:
                return 'large_square_object'
            else:
                return 'small_square_object'
        elif aspect_ratio > 2.0:
            return 'horizontal_object'
        elif aspect_ratio < 0.5:
            return 'vertical_object'
        else:
            return 'rectangular_object'
    
    def _analyze_frame(self, frame: np.ndarray) -> DetectionResult:
        """Analyze content in a single video frame.
        
        Args:
            frame: Video frame as numpy array
            
        Returns:
            DetectionResult for the frame
        """
        result = DetectionResult()
        
        # Detect faces if enabled
        if self.config.content.enable_face_detection:
            result.faces = self._detect_faces(frame)
        
        # Detect objects if enabled
        if self.config.content.enable_object_detection:
            result.objects = self._detect_objects(frame)
        
        # Classify scene if enabled
        if self.config.content.enable_scene_classification:
            result.scene_labels = self._classify_scene(frame)
        
        # Extract dominant colors
        result.dominant_colors = self._extract_dominant_colors(frame, k=3)
        
        return result
    
    def _deduplicate_faces(self, faces: List[FaceInfo]) -> List[FaceInfo]:
        """Remove duplicate face detections.
        
        Args:
            faces: List of detected faces
            
        Returns:
            List of deduplicated faces
        """
        if not faces:
            return []
        
        # Simple deduplication based on bbox overlap
        deduplicated = []
        
        for face in faces:
            is_duplicate = False
            for existing_face in deduplicated:
                if self._calculate_bbox_overlap(face.bbox, existing_face.bbox) > 0.5:
                    # Keep the one with higher confidence
                    if face.confidence > existing_face.confidence:
                        deduplicated.remove(existing_face)
                        deduplicated.append(face)
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                deduplicated.append(face)
        
        return deduplicated
    
    def _deduplicate_objects(self, objects: List[ObjectInfo]) -> List[ObjectInfo]:
        """Remove duplicate object detections.
        
        Args:
            objects: List of detected objects
            
        Returns:
            List of deduplicated objects
        """
        if not objects:
            return []
        
        # Group by class name and deduplicate within groups
        class_groups = {}
        for obj in objects:
            if obj.class_name not in class_groups:
                class_groups[obj.class_name] = []
            class_groups[obj.class_name].append(obj)
        
        deduplicated = []
        for class_name, class_objects in class_groups.items():
            # For each class, remove overlapping detections
            class_deduplicated = []
            for obj in class_objects:
                is_duplicate = False
                for existing_obj in class_deduplicated:
                    if self._calculate_bbox_overlap(obj.bbox, existing_obj.bbox) > 0.3:
                        # Keep the one with higher confidence
                        if obj.confidence > existing_obj.confidence:
                            class_deduplicated.remove(existing_obj)
                            class_deduplicated.append(obj)
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    class_deduplicated.append(obj)
            
            deduplicated.extend(class_deduplicated)
        
        return deduplicated
    
    def _aggregate_scene_labels(self, scene_labels: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        """Aggregate scene labels from multiple frames.
        
        Args:
            scene_labels: List of (label, confidence) tuples from all frames
            
        Returns:
            Aggregated scene labels with average confidence
        """
        if not scene_labels:
            return []
        
        # Group by label and average confidence
        label_groups = {}
        for label, confidence in scene_labels:
            if label not in label_groups:
                label_groups[label] = []
            label_groups[label].append(confidence)
        
        # Calculate average confidence for each label
        aggregated = []
        for label, confidences in label_groups.items():
            avg_confidence = np.mean(confidences)
            aggregated.append((label, avg_confidence))
        
        # Sort by confidence
        aggregated.sort(key=lambda x: x[1], reverse=True)
        
        return aggregated
    
    def _aggregate_colors(self, all_colors: List[Tuple[int, int, int]]) -> List[Tuple[int, int, int]]:
        """Aggregate dominant colors from multiple frames.
        
        Args:
            all_colors: List of RGB color tuples from all frames
            
        Returns:
            Aggregated dominant colors
        """
        if not all_colors:
            return []
        
        if not SKLEARN_AVAILABLE:
            # Fallback: return most common colors
            unique_colors = list(set(all_colors))
            return unique_colors[:5]
        
        try:
            # Use clustering to find dominant colors across all frames
            colors_array = np.array(all_colors)
            
            # Cluster colors
            k = min(5, len(unique_colors := list(set(all_colors))))
            if k <= 1:
                return unique_colors
            
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            kmeans.fit(colors_array)
            
            # Return cluster centers as dominant colors
            dominant_colors = []
            for color in kmeans.cluster_centers_:
                rgb = (int(color[0]), int(color[1]), int(color[2]))
                dominant_colors.append(rgb)
            
            return dominant_colors
            
        except Exception:
            # Fallback: return unique colors
            unique_colors = list(set(all_colors))
            return unique_colors[:5]
    
    def _generate_color_tags(self, colors: List[Tuple[int, int, int]]) -> List[str]:
        """Generate color-based tags from dominant colors.
        
        Args:
            colors: List of RGB color tuples
            
        Returns:
            List of color tags
        """
        color_tags = []
        
        for r, g, b in colors:
            # Simple color naming based on RGB values
            if r > 200 and g < 100 and b < 100:
                color_tags.append('red')
            elif g > 200 and r < 100 and b < 100:
                color_tags.append('green')
            elif b > 200 and r < 100 and g < 100:
                color_tags.append('blue')
            elif r > 200 and g > 200 and b < 100:
                color_tags.append('yellow')
            elif r > 150 and g > 150 and b > 150:
                color_tags.append('bright')
            elif r < 100 and g < 100 and b < 100:
                color_tags.append('dark')
        
        return list(set(color_tags))
    
    def _calculate_bbox_overlap(self, bbox1: Tuple[int, int, int, int], bbox2: Tuple[int, int, int, int]) -> float:
        """Calculate overlap ratio between two bounding boxes.
        
        Args:
            bbox1: First bounding box (x, y, w, h)
            bbox2: Second bounding box (x, y, w, h)
            
        Returns:
            Overlap ratio (0.0-1.0)
        """
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2
        
        # Calculate intersection
        x_left = max(x1, x2)
        y_top = max(y1, y2)
        x_right = min(x1 + w1, x2 + w2)
        y_bottom = min(y1 + h1, y2 + h2)
        
        if x_right <= x_left or y_bottom <= y_top:
            return 0.0
        
        intersection_area = (x_right - x_left) * (y_bottom - y_top)
        
        # Calculate union
        area1 = w1 * h1
        area2 = w2 * h2
        union_area = area1 + area2 - intersection_area
        
        return intersection_area / union_area if union_area > 0 else 0.0
    
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