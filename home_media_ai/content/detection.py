"""
Detection result data structures for content identification.

This module defines data structures for storing detection results from
various content identification algorithms including face detection,
object detection, and scene classification.

Classes:
    FaceInfo: Information about detected faces
    ObjectInfo: Information about detected objects
    DetectionResult: Container for all detection results
    
Example:
    >>> face = FaceInfo(
    ...     bbox=(100, 100, 50, 50),
    ...     confidence=0.95,
    ...     age_estimate=25
    ... )
    >>> result = DetectionResult(faces=[face])
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
import numpy as np


@dataclass
class FaceInfo:
    """Information about a detected face.
    
    Attributes:
        bbox: Bounding box as (x, y, width, height)
        confidence: Detection confidence score (0.0-1.0)
        landmarks: Facial landmark points if available
        age_estimate: Estimated age if available
        gender_estimate: Estimated gender if available
        emotion_estimate: Estimated emotion if available
        encoding: Face encoding vector for recognition
        quality_score: Face quality score (0.0-1.0)
        
    Example:
        >>> face = FaceInfo(
        ...     bbox=(100, 100, 50, 50),
        ...     confidence=0.95,
        ...     age_estimate=25,
        ...     gender_estimate='female'
        ... )
    """
    bbox: Tuple[int, int, int, int]  # (x, y, width, height)
    confidence: float
    landmarks: Optional[List[Tuple[int, int]]] = None
    age_estimate: Optional[int] = None
    gender_estimate: Optional[str] = None
    emotion_estimate: Optional[str] = None
    encoding: Optional[np.ndarray] = None
    quality_score: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert face info to dictionary format.
        
        Returns:
            Dictionary representation of face information
        """
        data = {
            'bbox': self.bbox,
            'confidence': self.confidence,
            'age_estimate': self.age_estimate,
            'gender_estimate': self.gender_estimate,
            'emotion_estimate': self.emotion_estimate,
            'quality_score': self.quality_score,
        }
        
        if self.landmarks:
            data['landmarks'] = self.landmarks
        
        if self.encoding is not None:
            data['encoding'] = self.encoding.tolist()
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FaceInfo':
        """Create FaceInfo instance from dictionary.
        
        Args:
            data: Dictionary containing face information
            
        Returns:
            FaceInfo instance
        """
        encoding = None
        if 'encoding' in data and data['encoding']:
            encoding = np.array(data['encoding'])
        
        return cls(
            bbox=tuple(data['bbox']),
            confidence=data['confidence'],
            landmarks=data.get('landmarks'),
            age_estimate=data.get('age_estimate'),
            gender_estimate=data.get('gender_estimate'),
            emotion_estimate=data.get('emotion_estimate'),
            encoding=encoding,
            quality_score=data.get('quality_score'),
        )


@dataclass
class ObjectInfo:
    """Information about a detected object.
    
    Attributes:
        bbox: Bounding box as (x, y, width, height)
        confidence: Detection confidence score (0.0-1.0)
        class_name: Name of the detected object class
        class_id: Numeric ID of the object class
        mask: Object segmentation mask if available
        
    Example:
        >>> obj = ObjectInfo(
        ...     bbox=(200, 150, 100, 80),
        ...     confidence=0.87,
        ...     class_name='dog',
        ...     class_id=16
        ... )
    """
    bbox: Tuple[int, int, int, int]  # (x, y, width, height)
    confidence: float
    class_name: str
    class_id: int
    mask: Optional[np.ndarray] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert object info to dictionary format.
        
        Returns:
            Dictionary representation of object information
        """
        data = {
            'bbox': self.bbox,
            'confidence': self.confidence,
            'class_name': self.class_name,
            'class_id': self.class_id,
        }
        
        if self.mask is not None:
            data['mask'] = self.mask.tolist()
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ObjectInfo':
        """Create ObjectInfo instance from dictionary.
        
        Args:
            data: Dictionary containing object information
            
        Returns:
            ObjectInfo instance
        """
        mask = None
        if 'mask' in data and data['mask']:
            mask = np.array(data['mask'])
        
        return cls(
            bbox=tuple(data['bbox']),
            confidence=data['confidence'],
            class_name=data['class_name'],
            class_id=data['class_id'],
            mask=mask,
        )


@dataclass
class DetectionResult:
    """Container for all content detection results.
    
    Attributes:
        faces: List of detected faces
        objects: List of detected objects
        scene_labels: List of scene classification labels with confidence
        text_content: Extracted text content from OCR
        dominant_colors: List of dominant colors in the image
        tags: Additional tags or metadata
        processing_time: Time taken for analysis in seconds
        
    Example:
        >>> result = DetectionResult(
        ...     faces=[face1, face2],
        ...     objects=[obj1, obj2, obj3],
        ...     scene_labels=[('outdoor', 0.92), ('park', 0.78)],
        ...     text_content='Happy Birthday!'
        ... )
    """
    faces: List[FaceInfo] = None
    objects: List[ObjectInfo] = None
    scene_labels: List[Tuple[str, float]] = None
    text_content: Optional[str] = None
    dominant_colors: List[Tuple[int, int, int]] = None
    tags: List[str] = None
    processing_time: Optional[float] = None
    
    def __post_init__(self):
        """Initialize empty lists for None values."""
        if self.faces is None:
            self.faces = []
        if self.objects is None:
            self.objects = []
        if self.scene_labels is None:
            self.scene_labels = []
        if self.dominant_colors is None:
            self.dominant_colors = []
        if self.tags is None:
            self.tags = []
    
    @property
    def has_faces(self) -> bool:
        """Check if any faces were detected."""
        return len(self.faces) > 0
    
    @property
    def has_objects(self) -> bool:
        """Check if any objects were detected."""
        return len(self.objects) > 0
    
    @property
    def has_text(self) -> bool:
        """Check if any text was detected."""
        return self.text_content is not None and len(self.text_content.strip()) > 0
    
    @property
    def face_count(self) -> int:
        """Get number of detected faces."""
        return len(self.faces)
    
    @property
    def object_count(self) -> int:
        """Get number of detected objects."""
        return len(self.objects)
    
    def get_high_confidence_faces(self, threshold: float = 0.8) -> List[FaceInfo]:
        """Get faces with confidence above threshold.
        
        Args:
            threshold: Minimum confidence threshold
            
        Returns:
            List of high-confidence faces
        """
        return [face for face in self.faces if face.confidence >= threshold]
    
    def get_high_confidence_objects(self, threshold: float = 0.7) -> List[ObjectInfo]:
        """Get objects with confidence above threshold.
        
        Args:
            threshold: Minimum confidence threshold
            
        Returns:
            List of high-confidence objects
        """
        return [obj for obj in self.objects if obj.confidence >= threshold]
    
    def get_object_classes(self) -> List[str]:
        """Get unique object class names.
        
        Returns:
            List of unique object class names
        """
        return list(set(obj.class_name for obj in self.objects))
    
    def get_scene_predictions(self, threshold: float = 0.5) -> List[str]:
        """Get scene labels with confidence above threshold.
        
        Args:
            threshold: Minimum confidence threshold
            
        Returns:
            List of scene labels
        """
        return [label for label, conf in self.scene_labels if conf >= threshold]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert detection result to dictionary format.
        
        Returns:
            Dictionary representation of all detection results
        """
        return {
            'faces': [face.to_dict() for face in self.faces],
            'objects': [obj.to_dict() for obj in self.objects],
            'scene_labels': self.scene_labels,
            'text_content': self.text_content,
            'dominant_colors': self.dominant_colors,
            'tags': self.tags,
            'processing_time': self.processing_time,
            'face_count': self.face_count,
            'object_count': self.object_count,
            'has_faces': self.has_faces,
            'has_objects': self.has_objects,
            'has_text': self.has_text,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DetectionResult':
        """Create DetectionResult instance from dictionary.
        
        Args:
            data: Dictionary containing detection results
            
        Returns:
            DetectionResult instance
        """
        faces = [FaceInfo.from_dict(face_data) for face_data in data.get('faces', [])]
        objects = [ObjectInfo.from_dict(obj_data) for obj_data in data.get('objects', [])]
        
        return cls(
            faces=faces,
            objects=objects,
            scene_labels=data.get('scene_labels', []),
            text_content=data.get('text_content'),
            dominant_colors=data.get('dominant_colors', []),
            tags=data.get('tags', []),
            processing_time=data.get('processing_time'),
        )