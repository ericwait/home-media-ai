"""
Quality metrics for images and videos.

This module defines data structures for storing quality assessment results
and provides methods for calculating overall quality scores.

Classes:
    ImageQualityMetrics: Container for image quality measurements
    VideoQualityMetrics: Container for video quality measurements
    
Example:
    >>> metrics = ImageQualityMetrics(
    ...     blur_score=85.0,
    ...     brightness_score=92.0,
    ...     contrast_score=78.0
    ... )
    >>> print(f"Overall quality: {metrics.overall_score}")
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
import numpy as np


@dataclass
class ImageQualityMetrics:
    """Container for image quality assessment metrics.
    
    Attributes:
        blur_score: Blur quality score (0-100, higher is better)
        brightness_score: Brightness quality score (0-100)
        contrast_score: Contrast quality score (0-100)
        noise_score: Noise quality score (0-100, higher is less noise)
        sharpness_score: Sharpness quality score (0-100)
        saturation_score: Color saturation score (0-100)
        exposure_score: Exposure quality score (0-100)
        face_quality_score: Face quality score if faces detected (0-100)
        overall_score: Computed overall quality score (0-100)
        
    Example:
        >>> metrics = ImageQualityMetrics(
        ...     blur_score=85.0,
        ...     brightness_score=92.0,
        ...     contrast_score=78.0
        ... )
        >>> print(f"Quality: {metrics.overall_score}/100")
    """
    blur_score: float = 0.0
    brightness_score: float = 0.0
    contrast_score: float = 0.0
    noise_score: float = 0.0
    sharpness_score: float = 0.0
    saturation_score: float = 0.0
    exposure_score: float = 0.0
    face_quality_score: Optional[float] = None
    _overall_score: Optional[float] = None
    
    @property
    def overall_score(self) -> float:
        """Calculate overall quality score from individual metrics.
        
        Returns:
            Overall quality score (0-100) as weighted average of metrics
        """
        if self._overall_score is not None:
            return self._overall_score
        
        # Define weights for different quality aspects
        weights = {
            'blur_score': 0.25,
            'brightness_score': 0.15,
            'contrast_score': 0.15,
            'noise_score': 0.15,
            'sharpness_score': 0.20,
            'saturation_score': 0.05,
            'exposure_score': 0.05,
        }
        
        # Calculate weighted average
        total_score = 0.0
        total_weight = 0.0
        
        for metric, weight in weights.items():
            score = getattr(self, metric)
            if score > 0:  # Only include metrics that were calculated
                total_score += score * weight
                total_weight += weight
        
        # Include face quality if available (bonus scoring)
        if self.face_quality_score is not None and self.face_quality_score > 0:
            total_score += self.face_quality_score * 0.1
            total_weight += 0.1
        
        self._overall_score = total_score / total_weight if total_weight > 0 else 0.0
        return self._overall_score
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary format.
        
        Returns:
            Dictionary containing all metric values
        """
        return {
            'blur_score': self.blur_score,
            'brightness_score': self.brightness_score,
            'contrast_score': self.contrast_score,
            'noise_score': self.noise_score,
            'sharpness_score': self.sharpness_score,
            'saturation_score': self.saturation_score,
            'exposure_score': self.exposure_score,
            'face_quality_score': self.face_quality_score,
            'overall_score': self.overall_score,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImageQualityMetrics':
        """Create metrics instance from dictionary.
        
        Args:
            data: Dictionary containing metric values
            
        Returns:
            ImageQualityMetrics instance
        """
        return cls(
            blur_score=data.get('blur_score', 0.0),
            brightness_score=data.get('brightness_score', 0.0),
            contrast_score=data.get('contrast_score', 0.0),
            noise_score=data.get('noise_score', 0.0),
            sharpness_score=data.get('sharpness_score', 0.0),
            saturation_score=data.get('saturation_score', 0.0),
            exposure_score=data.get('exposure_score', 0.0),
            face_quality_score=data.get('face_quality_score'),
        )


@dataclass
class VideoQualityMetrics:
    """Container for video quality assessment metrics.
    
    Attributes:
        avg_frame_quality: Average quality score across sampled frames (0-100)
        motion_blur_score: Motion blur assessment score (0-100)
        stability_score: Video stability/shakiness score (0-100)
        audio_quality_score: Audio quality score if audio present (0-100)
        compression_score: Video compression quality score (0-100)
        frame_consistency_score: Consistency between frames (0-100)
        duration_seconds: Video duration in seconds
        frame_rate: Video frame rate (fps)
        resolution_width: Video width in pixels
        resolution_height: Video height in pixels
        overall_score: Computed overall quality score (0-100)
        
    Example:
        >>> metrics = VideoQualityMetrics(
        ...     avg_frame_quality=85.0,
        ...     stability_score=92.0,
        ...     duration_seconds=30.5
        ... )
        >>> print(f"Video quality: {metrics.overall_score}/100")
    """
    avg_frame_quality: float = 0.0
    motion_blur_score: float = 0.0
    stability_score: float = 0.0
    audio_quality_score: Optional[float] = None
    compression_score: float = 0.0
    frame_consistency_score: float = 0.0
    duration_seconds: float = 0.0
    frame_rate: float = 0.0
    resolution_width: int = 0
    resolution_height: int = 0
    _overall_score: Optional[float] = None
    
    @property
    def overall_score(self) -> float:
        """Calculate overall video quality score from individual metrics.
        
        Returns:
            Overall quality score (0-100) as weighted average of metrics
        """
        if self._overall_score is not None:
            return self._overall_score
        
        # Define weights for different quality aspects
        weights = {
            'avg_frame_quality': 0.30,
            'motion_blur_score': 0.20,
            'stability_score': 0.25,
            'compression_score': 0.15,
            'frame_consistency_score': 0.10,
        }
        
        # Calculate weighted average
        total_score = 0.0
        total_weight = 0.0
        
        for metric, weight in weights.items():
            score = getattr(self, metric)
            if score > 0:  # Only include metrics that were calculated
                total_score += score * weight
                total_weight += weight
        
        # Include audio quality if available
        if self.audio_quality_score is not None and self.audio_quality_score > 0:
            total_score += self.audio_quality_score * 0.1
            total_weight += 0.1
        
        self._overall_score = total_score / total_weight if total_weight > 0 else 0.0
        return self._overall_score
    
    @property
    def resolution_score(self) -> float:
        """Calculate resolution quality score based on pixel count.
        
        Returns:
            Resolution score (0-100) based on total pixels
        """
        total_pixels = self.resolution_width * self.resolution_height
        
        # Define resolution quality thresholds
        if total_pixels >= 3840 * 2160:  # 4K
            return 100.0
        elif total_pixels >= 1920 * 1080:  # 1080p
            return 85.0
        elif total_pixels >= 1280 * 720:  # 720p
            return 70.0
        elif total_pixels >= 854 * 480:  # 480p
            return 50.0
        elif total_pixels >= 640 * 360:  # 360p
            return 30.0
        else:
            return 15.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary format.
        
        Returns:
            Dictionary containing all metric values
        """
        return {
            'avg_frame_quality': self.avg_frame_quality,
            'motion_blur_score': self.motion_blur_score,
            'stability_score': self.stability_score,
            'audio_quality_score': self.audio_quality_score,
            'compression_score': self.compression_score,
            'frame_consistency_score': self.frame_consistency_score,
            'duration_seconds': self.duration_seconds,
            'frame_rate': self.frame_rate,
            'resolution_width': self.resolution_width,
            'resolution_height': self.resolution_height,
            'resolution_score': self.resolution_score,
            'overall_score': self.overall_score,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VideoQualityMetrics':
        """Create metrics instance from dictionary.
        
        Args:
            data: Dictionary containing metric values
            
        Returns:
            VideoQualityMetrics instance
        """
        return cls(
            avg_frame_quality=data.get('avg_frame_quality', 0.0),
            motion_blur_score=data.get('motion_blur_score', 0.0),
            stability_score=data.get('stability_score', 0.0),
            audio_quality_score=data.get('audio_quality_score'),
            compression_score=data.get('compression_score', 0.0),
            frame_consistency_score=data.get('frame_consistency_score', 0.0),
            duration_seconds=data.get('duration_seconds', 0.0),
            frame_rate=data.get('frame_rate', 0.0),
            resolution_width=data.get('resolution_width', 0),
            resolution_height=data.get('resolution_height', 0),
        )