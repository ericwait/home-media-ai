#!/usr/bin/env python3
"""
Unit tests for ExifExtractor class.

Run with pytest:
    pytest tests/test_exif_extractor.py -v

Or with unittest:
    python -m unittest tests.test_exif_extractor
"""

import unittest
import tempfile
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "python"))

from home_media_ai.exif_extractor import ExifExtractor


class TestExifExtractor(unittest.TestCase):
    """Test ExifExtractor metadata extraction."""

    def setUp(self):
        """Initialize extractor for each test."""
        self.extractor = ExifExtractor()

    def test_normalize_rating_valid_values(self):
        """Test rating normalization with valid inputs."""
        self.assertEqual(self.extractor._normalize_rating(3), 3)
        self.assertEqual(self.extractor._normalize_rating("4"), 4)
        self.assertEqual(self.extractor._normalize_rating(5), 5)
        self.assertEqual(self.extractor._normalize_rating(0), 0)

    def test_normalize_rating_percentage(self):
        """Test rating normalization from percentage scale."""
        self.assertEqual(self.extractor._normalize_rating(80), 4)  # 80/20 = 4
        self.assertEqual(self.extractor._normalize_rating(100), 5)  # 100/20 = 5
        self.assertEqual(self.extractor._normalize_rating(60), 3)   # 60/20 = 3

    def test_normalize_rating_invalid_values(self):
        """Test rating normalization with invalid inputs."""
        self.assertIsNone(self.extractor._normalize_rating(None))
        self.assertIsNone(self.extractor._normalize_rating(""))
        self.assertIsNone(self.extractor._normalize_rating("invalid"))
        self.assertEqual(self.extractor._normalize_rating(101), None)  # Invalid high rating
        self.assertEqual(self.extractor._normalize_rating(-1), None)  # Negative ratings are invalid

    def test_normalize_rating_clamping(self):
        """Test rating values are clamped to 0-5 range."""

        # Negative values should return None
        self.assertIsNone(self.extractor._normalize_rating(-1))

        # Values between 6-100 are treated as percentages
        # 10% = 0.5, rounds to 1 star
        self.assertEqual(self.extractor._normalize_rating(10), 1)

    def test_parse_xmp_gps_coord_valid(self):
        """Test XMP GPS coordinate parsing with valid formats."""
        # Darktable format: "43,11.302350N"
        result = self.extractor._parse_xmp_gps_coord("43,11.302350N")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, 43.188372, places=5)

        # West longitude
        result = self.extractor._parse_xmp_gps_coord("89,16.869078W")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, -89.281151, places=5)

        # South latitude
        result = self.extractor._parse_xmp_gps_coord("34,52.5S")
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result, -34.875, places=5)

    def test_parse_xmp_gps_coord_invalid(self):
        """Test XMP GPS coordinate parsing with invalid inputs."""
        self.assertIsNone(self.extractor._parse_xmp_gps_coord(""))
        self.assertIsNone(self.extractor._parse_xmp_gps_coord("invalid"))
        self.assertIsNone(self.extractor._parse_xmp_gps_coord("43N"))
        self.assertIsNone(self.extractor._parse_xmp_gps_coord("43,"))

    def test_convert_rational_valid(self):
        """Test rational number conversion with valid inputs."""
        self.assertEqual(self.extractor._convert_rational((10, 2)), 5.0)
        self.assertEqual(self.extractor._convert_rational((1, 4)), 0.25)
        self.assertEqual(self.extractor._convert_rational(2.8), 2.8)

    def test_convert_rational_invalid(self):
        """Test rational number conversion with invalid inputs."""
        self.assertIsNone(self.extractor._convert_rational((1, 0)))  # Division by zero
        self.assertIsNone(self.extractor._convert_rational(None))
        self.assertIsNone(self.extractor._convert_rational("invalid"))

    def test_format_shutter_speed(self):
        """Test shutter speed formatting."""
        self.assertEqual(self.extractor._format_shutter_speed((1, 1000)), "1/1000")
        self.assertEqual(self.extractor._format_shutter_speed((1, 60)), "1/60")
        self.assertEqual(self.extractor._format_shutter_speed(2.5), "2.5")

    def test_extract_metadata_nonexistent_file(self):
        """Test extraction on nonexistent file returns empty dict."""
        result = self.extractor.extract_metadata("/nonexistent/file.jpg")
        self.assertIsInstance(result, dict)
        # Should return empty dict or dict with no critical fields
        # (PIL/exifread will fail gracefully)

    def test_xmp_sidecar_not_found(self):
        """Test XMP extraction when sidecar doesn't exist."""
        with tempfile.NamedTemporaryFile(suffix='.jpg') as tmp:
            result = self.extractor._extract_xmp_sidecar(tmp.name)
            self.assertEqual(result, {})


class TestXMPParsing(unittest.TestCase):
    """Test XMP sidecar file parsing."""

    def setUp(self):
        """Initialize extractor and temp directory."""
        self.extractor = ExifExtractor()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_xmp_file(self, base_name: str, xmp_content: str) -> str:
        """Helper to create a temporary XMP sidecar file.

        Args:
            base_name: Base filename (e.g., 'test.jpg')
            xmp_content: XML content for the XMP file

        Returns:
            Path to the base file (XMP will be base_name + '.xmp')
        """
        base_path = Path(self.temp_dir) / base_name
        xmp_path = Path(str(base_path) + '.xmp')

        # Create empty base file
        base_path.touch()

        # Create XMP sidecar
        xmp_path.write_text(xmp_content)

        return str(base_path)

    def test_darktable_xmp_rating(self):
        """Test rating extraction from Darktable XMP format."""
        xmp_content = '''<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="XMP Core 4.4.0-Exiv2">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmp:Rating="4"/>
 </rdf:RDF>
</x:xmpmeta>'''

        file_path = self.create_xmp_file('test.dng', xmp_content)
        metadata = self.extractor._extract_xmp_sidecar(file_path)

        self.assertEqual(metadata.get('rating'), 4)

    def test_darktable_xmp_gps(self):
        """Test GPS extraction from Darktable XMP format."""
        xmp_content = '''<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description
    xmlns:exif="http://ns.adobe.com/exif/1.0/"
    exif:GPSLatitude="43,11.302350N"
    exif:GPSLongitude="89,16.869078W"
    exif:GPSAltitude="2594/10"/>
 </rdf:RDF>
</x:xmpmeta>'''

        file_path = self.create_xmp_file('test.dng', xmp_content)
        metadata = self.extractor._extract_xmp_sidecar(file_path)

        self.assertAlmostEqual(metadata.get('gps_latitude'), 43.188372, places=5)
        self.assertAlmostEqual(metadata.get('gps_longitude'), -89.281151, places=5)
        self.assertAlmostEqual(metadata.get('gps_altitude'), 259.4, places=1)

    def test_lightroom_xmp_keywords(self):
        """Test keyword extraction from Lightroom XMP format."""
        xmp_content = '''<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/">
   <dc:subject>
    <rdf:Bag>
     <rdf:li>sedges</rdf:li>
     <rdf:li>wetland</rdf:li>
     <rdf:li>carex</rdf:li>
    </rdf:Bag>
   </dc:subject>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>'''

        file_path = self.create_xmp_file('test.jpg', xmp_content)
        metadata = self.extractor._extract_xmp_sidecar(file_path)

        self.assertEqual(metadata.get('keywords'), ['sedges', 'wetland', 'carex'])

    def test_hierarchical_keywords(self):
        """Test hierarchical keyword extraction."""
        xmp_content = '''<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description xmlns:lr="http://ns.adobe.com/lightroom/1.0/">
   <lr:hierarchicalSubject>
    <rdf:Bag>
     <rdf:li>plants|cyperaceae|carex</rdf:li>
     <rdf:li>location|wisconsin|madison</rdf:li>
    </rdf:Bag>
   </lr:hierarchicalSubject>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>'''

        file_path = self.create_xmp_file('test.jpg', xmp_content)
        metadata = self.extractor._extract_xmp_sidecar(file_path)

        expected = ['plants|cyperaceae|carex', 'location|wisconsin|madison']
        self.assertEqual(metadata.get('hierarchical_keywords'), expected)

    def test_malformed_xmp(self):
        """Test handling of malformed XMP files."""
        xmp_content = '''<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description>
   <!-- Missing closing tags -->
</x:xmpmeta>'''

        file_path = self.create_xmp_file('test.jpg', xmp_content)
        metadata = self.extractor._extract_xmp_sidecar(file_path)

        # Should return empty dict on parse error
        self.assertEqual(metadata, {})


if __name__ == '__main__':
    unittest.main()
