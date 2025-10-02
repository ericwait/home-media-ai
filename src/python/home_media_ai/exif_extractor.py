"""EXIF and XMP metadata extraction for media files.

This module handles extraction of metadata from image files and their
associated XMP sidecar files (commonly used by Lightroom and other
photo management software).
"""

import decimal
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional

# Import shared constants
try:
    from .constants import RAW_EXTENSIONS
except ImportError:
    # Fallback if constants module not available
    RAW_EXTENSIONS = {'.dng', '.cr2', '.nef', '.arw'}

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import exifread
    HAS_EXIFREAD = True
except ImportError:
    HAS_EXIFREAD = False

try:
    import rawpy
    HAS_RAWPY = True
except ImportError:
    HAS_RAWPY = False


logger = logging.getLogger(__name__)


class ExifExtractor:
    """Extracts EXIF metadata from image files and XMP sidecar files.

    Supports multiple extraction methods (PIL, exifread) and XMP sidecar
    parsing for Lightroom-style metadata storage.

    Attributes:
        RATING_TAGS: List of EXIF tag names that contain rating information.
        XMP_NAMESPACES: XML namespaces used in XMP files.
    """

    # EXIF tags that may contain rating information
    RATING_TAGS = ['Rating', 'RatingPercent']

    # XMP namespaces for parsing sidecar files
    XMP_NAMESPACES = {
        'x': 'adobe:ns:meta/',
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'xmp': 'http://ns.adobe.com/xap/1.0/',
        'dc': 'http://purl.org/dc/elements/1.1/',
        'exif': 'http://ns.adobe.com/exif/1.0/',
        'photoshop': 'http://ns.adobe.com/photoshop/1.0/',
        'aux': 'http://ns.adobe.com/exif/1.0/aux/',
        'lr': 'http://ns.adobe.com/lightroom/1.0/',
        'tiff': 'http://ns.adobe.com/tiff/1.0/',
    }

    def extract_metadata(self, file_path: str) -> Dict:
        """Extracts comprehensive metadata from an image file and its sidecar.

        Tries multiple extraction methods and merges results, with XMP sidecar
        taking precedence for overlapping fields (as it contains user edits).

        Args:
            file_path: Path to the image file.

        Returns:
            Dict: Combined metadata from all sources.
        """
        metadata = {}

        # Extract from embedded EXIF
        if HAS_PIL:
            metadata.update(self._extract_exif_pil(file_path))

        if HAS_EXIFREAD:
            metadata.update(self._extract_exif_exifread(file_path))

        # Extract from XMP sidecar (overrides embedded data)
        xmp_metadata = self._extract_xmp_sidecar(file_path)
        if xmp_metadata:
            metadata.update(xmp_metadata)

        # For RAW files, use rawpy to get true image dimensions
        # This overrides any thumbnail dimensions that may have been extracted
        file_ext = Path(file_path).suffix.lower()
        if file_ext in RAW_EXTENSIONS and HAS_RAWPY:
            try:
                with rawpy.imread(file_path) as raw:
                    # Use visible image dimensions (after crop)
                    metadata['width'] = raw.sizes.width
                    metadata['height'] = raw.sizes.height
                    logger.debug(f"Extracted RAW dimensions: {raw.sizes.width}x{raw.sizes.height}")
            except Exception as e:
                logger.debug(f"Failed to extract RAW dimensions from {file_path}: {e}")

        return metadata

    def _extract_exif_pil(self, file_path: str) -> Dict:
        """Extracts EXIF metadata using PIL/Pillow.

        Args:
            file_path: Path to the image file.

        Returns:
            Dict: Extracted EXIF metadata.
        """
        metadata = {}

        try:
            with Image.open(file_path) as img:
                exif_data = None
                if hasattr(img, 'getexif'):
                    try:
                        exif_data = img.getexif()
                    except Exception:
                        pass

                # Fall back to legacy API (JPEG only)
                if exif_data is None and hasattr(img, '_getexif'):
                    try:
                        exif_data = img._getexif()
                    except Exception:
                        return metadata

                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)

                    # GPS coordinates
                    if tag == 'GPSInfo':
                        gps = self._parse_gps_info(value)
                        if gps:
                            metadata.update(gps)

                    # Camera information
                    elif tag == 'Make':
                        metadata['camera_make'] = str(value).strip()
                    elif tag == 'Model':
                        metadata['camera_model'] = str(value).strip()
                    elif tag == 'LensModel':
                        metadata['lens_model'] = str(value).strip()

                    # Exposure settings
                    elif tag == 'FNumber':
                        metadata['aperture'] = self._convert_rational(value)
                    elif tag == 'ExposureTime':
                        metadata['shutter_speed'] = self._format_shutter_speed(value)
                    elif tag == 'ISOSpeedRatings':
                        metadata['iso'] = int(value)
                    elif tag == 'FocalLength':
                        metadata['focal_length'] = self._convert_rational(value)

                    # Image dimensions
                    elif tag == 'ExifImageWidth':
                        metadata['width'] = int(value)
                    elif tag == 'ExifImageHeight':
                        metadata['height'] = int(value)

                    # Rating
                    elif tag in self.RATING_TAGS:
                        metadata['rating'] = self._normalize_rating(value)

                    # Software
                    elif tag == 'Software':
                        metadata['software'] = str(value).strip()

                    # Orientation
                    elif tag == 'Orientation':
                        metadata['orientation'] = int(value)

        except (OSError, IOError) as e:
            logger.debug(f"PIL EXIF extraction failed for {file_path}: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error extracting PIL EXIF from {file_path}: {e}")

        return metadata

    def _extract_exif_exifread(self, file_path: str) -> Dict:
        """Extracts EXIF metadata using exifread (better for RAW files).

        Args:
            file_path: Path to the image file.

        Returns:
            Dict: Extracted EXIF metadata.
        """
        metadata = {}

        try:
            with open(file_path, 'rb') as f:
                tags = exifread.process_file(f, details=True)

                # GPS coordinates
                if 'GPS GPSLatitude' in tags and 'GPS GPSLongitude' in tags:
                    lat = self._convert_gps_coord(
                        tags['GPS GPSLatitude'],
                        tags.get('GPS GPSLatitudeRef')
                    )
                    lon = self._convert_gps_coord(
                        tags['GPS GPSLongitude'],
                        tags.get('GPS GPSLongitudeRef')
                    )
                    if lat and lon:
                        metadata['gps_latitude'] = lat
                        metadata['gps_longitude'] = lon

                    if 'GPS GPSAltitude' in tags:
                        altitude_value = tags['GPS GPSAltitude'].values[0]
                        metadata['gps_altitude'] = float(altitude_value.num) / float(altitude_value.den)

                # Camera info
                if 'Image Make' in tags:
                    metadata['camera_make'] = str(tags['Image Make']).strip()
                if 'Image Model' in tags:
                    metadata['camera_model'] = str(tags['Image Model']).strip()
                if 'EXIF LensModel' in tags:
                    metadata['lens_model'] = str(tags['EXIF LensModel']).strip()

                # Exposure settings
                if 'EXIF FNumber' in tags:
                    f_value = tags['EXIF FNumber'].values[0]
                    metadata['aperture'] = float(f_value.num) / float(f_value.den)
                if 'EXIF ExposureTime' in tags:
                    exp = tags['EXIF ExposureTime'].values[0]
                    metadata['shutter_speed'] = f"{exp.num}/{exp.den}"
                if 'EXIF ISOSpeedRatings' in tags:
                    metadata['iso'] = int(str(tags['EXIF ISOSpeedRatings']))
                if 'EXIF FocalLength' in tags:
                    focal = tags['EXIF FocalLength'].values[0]
                    metadata['focal_length'] = float(focal.num) / float(focal.den)

                # Dimensions - try multiple tag names for RAW file compatibility
                if 'EXIF ExifImageWidth' in tags:
                    metadata['width'] = int(str(tags['EXIF ExifImageWidth']))
                elif 'Image ImageWidth' in tags:
                    metadata['width'] = int(str(tags['Image ImageWidth']))
                elif 'EXIF PixelXDimension' in tags:
                    metadata['width'] = int(str(tags['EXIF PixelXDimension']))

                if 'EXIF ExifImageLength' in tags:
                    metadata['height'] = int(str(tags['EXIF ExifImageLength']))
                elif 'Image ImageLength' in tags:
                    metadata['height'] = int(str(tags['Image ImageLength']))
                elif 'EXIF PixelYDimension' in tags:
                    metadata['height'] = int(str(tags['EXIF PixelYDimension']))

                # Rating
                for rating_tag in ['Image Rating', 'Image RatingPercent', 'XMP Rating']:
                    if rating_tag in tags:
                        metadata['rating'] = self._normalize_rating(str(tags[rating_tag]))
                        break

        except (OSError, IOError) as e:
            logger.debug(f"exifread extraction failed for {file_path}: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error extracting exifread EXIF from {file_path}: {e}")

        return metadata

    def _extract_xmp_sidecar(self, file_path: str) -> Dict:
        """Extracts metadata from XMP sidecar file (Lightroom, Darktable, etc.).

        Lightroom stores edits and ratings in .xmp files alongside the original.
        Example: IMG_001.CR2 has sidecar IMG_001.CR2.xmp

        Darktable uses similar format but with attributes instead of elements.

        Args:
            file_path: Path to the image file (sidecar path derived from this).

        Returns:
            Dict: Metadata extracted from XMP sidecar, or empty dict if not found.
        """
        xmp_path = Path(file_path).with_suffix(Path(file_path).suffix + '.xmp')

        if not xmp_path.exists():
            return {}

        logger.debug(f"Found XMP sidecar: {xmp_path}")

        metadata = {}

        try:
            tree = ET.parse(xmp_path)
            root = tree.getroot()

            # Register namespaces for XPath queries
            for prefix, uri in self.XMP_NAMESPACES.items():
                ET.register_namespace(prefix, uri)

            # Find the Description element (works for both Lightroom and Darktable)
            desc = root.find('.//rdf:Description', self.XMP_NAMESPACES)
            if desc is None:
                return metadata

            # Extract rating - check both element and attribute formats
            # Darktable uses: xmp:Rating="3" (attribute)
            # Lightroom uses: <xmp:Rating>3</xmp:Rating> (element)
            rating = desc.get('{http://ns.adobe.com/xap/1.0/}Rating')
            if rating:
                metadata['rating'] = self._normalize_rating(rating)
            else:
                rating_elem = root.find('.//xmp:Rating', self.XMP_NAMESPACES)
                if rating_elem is not None and rating_elem.text:
                    metadata['rating'] = self._normalize_rating(rating_elem.text)

            # Extract GPS - Darktable stores as attributes
            gps_lat = desc.get('{http://ns.adobe.com/exif/1.0/}GPSLatitude')
            if gps_lat:
                metadata['gps_latitude'] = self._parse_xmp_gps_coord(gps_lat)

            gps_lon = desc.get('{http://ns.adobe.com/exif/1.0/}GPSLongitude')
            if gps_lon:
                metadata['gps_longitude'] = self._parse_xmp_gps_coord(gps_lon)

            gps_alt = desc.get('{http://ns.adobe.com/exif/1.0/}GPSAltitude')
            if gps_alt:
                # Format: "2594/10" (fraction)
                try:
                    if '/' in gps_alt:
                        num, den = gps_alt.split('/')
                        metadata['gps_altitude'] = float(num) / float(den)
                    else:
                        metadata['gps_altitude'] = float(gps_alt)
                except (ValueError, ZeroDivisionError):
                    pass

            # Extract camera info - try element format first, then attributes
            make_elem = root.find('.//exif:Make', self.XMP_NAMESPACES)
            if make_elem is not None and make_elem.text:
                metadata['camera_make'] = make_elem.text.strip()

            model_elem = root.find('.//exif:Model', self.XMP_NAMESPACES)
            if model_elem is not None and model_elem.text:
                metadata['camera_model'] = model_elem.text.strip()

            # Extract lens model
            lens_elem = root.find('.//aux:Lens', self.XMP_NAMESPACES)
            if lens_elem is not None and lens_elem.text:
                metadata['lens_model'] = lens_elem.text.strip()

            # Extract dimensions from XMP (especially useful for DNG/RAW files)
            # Try tiff:ImageWidth and tiff:ImageLength
            width_attr = desc.get('{http://ns.adobe.com/tiff/1.0/}ImageWidth')
            if width_attr:
                try:
                    metadata['width'] = int(width_attr)
                except ValueError:
                    pass

            height_attr = desc.get('{http://ns.adobe.com/tiff/1.0/}ImageLength')
            if height_attr:
                try:
                    metadata['height'] = int(height_attr)
                except ValueError:
                    pass

            # Also try exif:PixelXDimension and exif:PixelYDimension
            if 'width' not in metadata:
                width_elem = root.find('.//exif:PixelXDimension', self.XMP_NAMESPACES)
                if width_elem is not None and width_elem.text:
                    try:
                        metadata['width'] = int(width_elem.text)
                    except ValueError:
                        pass

            if 'height' not in metadata:
                height_elem = root.find('.//exif:PixelYDimension', self.XMP_NAMESPACES)
                if height_elem is not None and height_elem.text:
                    try:
                        metadata['height'] = int(height_elem.text)
                    except ValueError:
                        pass

            # Keywords/tags - works for both Lightroom and Darktable
            keywords = root.findall('.//dc:subject/rdf:Bag/rdf:li', self.XMP_NAMESPACES)
            if keywords:
                metadata['keywords'] = [kw.text.strip() for kw in keywords if kw.text]

            # Hierarchical keywords (Lightroom format)
            # Darktable uses lr:hierarchicalSubject with pipe-separated paths
            hier_keywords = root.findall('.//lr:hierarchicalSubject/rdf:Bag/rdf:li', self.XMP_NAMESPACES)
            if hier_keywords:
                metadata['hierarchical_keywords'] = [kw.text.strip() for kw in hier_keywords if kw.text]

            logger.info(f"Extracted XMP metadata from {xmp_path}")

        except ET.ParseError as e:
            logger.warning(f"Failed to parse XMP file {xmp_path}: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error reading XMP {xmp_path}: {e}")

        return metadata

    def _parse_gps_info(self, gps_info: Dict) -> Optional[Dict]:
        """Parses GPS information from PIL EXIF data.

        Args:
            gps_info: GPS info dictionary from EXIF.

        Returns:
            Optional[Dict]: Dictionary with gps_latitude, gps_longitude, gps_altitude.
        """
        try:
            def convert_to_degrees(value):
                d, m, s = value
                return float(d) + float(m) / 60.0 + float(s) / 3600.0

            gps_data = {}

            if 1 in gps_info and 2 in gps_info:  # Latitude
                lat = convert_to_degrees(gps_info[2])
                if gps_info[1] == 'S':
                    lat = -lat
                gps_data['gps_latitude'] = lat

            if 3 in gps_info and 4 in gps_info:  # Longitude
                lon = convert_to_degrees(gps_info[4])
                if gps_info[3] == 'W':
                    lon = -lon
                gps_data['gps_longitude'] = lon

            if 5 in gps_info and 6 in gps_info:  # Altitude
                altitude = float(gps_info[6])
                if gps_info[5] == 1:  # Below sea level
                    altitude = -altitude
                gps_data['gps_altitude'] = altitude

            return gps_data if gps_data else None
        except (KeyError, ValueError, TypeError) as e:
            logger.debug(f"Failed to parse GPS info: {e}")
            return None

    def _convert_gps_coord(self, coord, ref) -> Optional[float]:
        """Converts GPS coordinate from exifread format to decimal degrees.

        Args:
            coord: GPS coordinate values from exifread.
            ref: Reference direction (N/S for latitude, E/W for longitude).

        Returns:
            Optional[float]: Coordinate in decimal degrees.
        """
        try:
            degrees = float(coord.values[0].num) / float(coord.values[0].den)
            minutes = float(coord.values[1].num) / float(coord.values[1].den)
            seconds = float(coord.values[2].num) / float(coord.values[2].den)

            gps_decimal = degrees + minutes / 60.0 + seconds / 3600.0

            if ref and str(ref) in ['S', 'W']:
                gps_decimal = -gps_decimal

            return gps_decimal
        except (AttributeError, ValueError, ZeroDivisionError) as e:
            logger.debug(f"Failed to convert GPS coordinate: {e}")
            return None

    def _parse_xmp_gps_coord(self, coord_str: str) -> Optional[float]:
        """Parses GPS coordinate from XMP format.

        XMP stores GPS as strings like "43,30.5N" or "89,24.3W"

        Args:
            coord_str: GPS coordinate string from XMP.

        Returns:
            Optional[float]: Coordinate in decimal degrees.
        """
        try:
            # Remove direction letter
            direction = coord_str[-1] if coord_str[-1] in 'NSEW' else None
            coord_str = coord_str.rstrip('NSEW')

            # Parse degrees,minutes format
            parts = coord_str.split(',')
            if len(parts) == 2:
                degrees = float(parts[0])
                minutes = float(parts[1])
                decimal_degree = degrees + minutes / 60.0

                if direction in ['S', 'W']:
                    decimal_degree = -decimal_degree

                return decimal_degree
        except (ValueError, IndexError) as e:
            logger.debug(f"Failed to parse XMP GPS coordinate '{coord_str}': {e}")

        return None

    def _convert_rational(self, value) -> Optional[float]:
        """Converts rational number (tuple) to float.

        Args:
            value: Rational number as tuple (numerator, denominator) or float.

        Returns:
            Optional[float]: Converted value.
        """
        try:
            if isinstance(value, tuple) and len(value) == 2:
                return float(value[0]) / float(value[1])
            return float(value)
        except (ValueError, ZeroDivisionError, TypeError):
            return None

    def _format_shutter_speed(self, value) -> Optional[str]:
        """Formats shutter speed as a string.

        Args:
            value: Shutter speed as tuple or number.

        Returns:
            Optional[str]: Formatted shutter speed like "1/1000" or "2.5".
        """
        try:
            if isinstance(value, tuple) and len(value) == 2:
                return f"{value[0]}/{value[1]}"
            return str(value)
        except (ValueError, TypeError):
            return None

    def _normalize_rating(self, rating_value) -> Optional[int]:
        """Normalizes rating to 0-5 scale.

        Different software stores ratings differently:
        - XMP Rating: 0-5 (standard)
        - Windows: 0-5 stars
        - RatingPercent: 0-100 (convert to 0-5)

        Args:
            rating_value: Raw rating value from EXIF/XMP.

        Returns:
            Optional[int]: Rating normalized to 0-5 scale, or None if invalid.
        """
        try:
            # Handle None and empty strings
            if rating_value is None or rating_value == '':
                return None

            # Strip whitespace from strings
            if isinstance(rating_value, str):
                rating_value = rating_value.strip()
                if not rating_value:
                    return None

            # Convert to int
            rating = int(rating_value)

            # Valid range: 0-100
            if rating < 0 or rating > 100:
                return None

            # Convert percentage to 0-5 scale (values 6-100)
            if rating > 5:
                # Use Decimal for proper ROUND_HALF_UP behavior
                rating = int(
                    decimal.Decimal(rating / 20.0).quantize(
                        decimal.Decimal('1'),
                        rounding=decimal.ROUND_HALF_UP
                    )
                )

            # Clamp to 0-5 (defensive)
            return max(0, min(5, rating))

        except (ValueError, TypeError):
            return None
