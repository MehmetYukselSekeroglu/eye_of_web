"""
utils/file_utils.py birim testleri.
Çalıştır: python -m pytest tests/
"""
import pytest
from utils.file_utils import sanitize_filename, safe_save_path


class TestSanitizeFilename:
    def test_normal_name(self):
        assert sanitize_filename("ahmet") == "ahmet"

    def test_uppercase_converted(self):
        assert sanitize_filename("AHMET") == "ahmet"

    def test_turkish_chars(self):
        result = sanitize_filename("çğıöşü")
        assert ".." not in result
        assert "/" not in result

    def test_path_traversal_blocked(self):
        result = sanitize_filename("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_spaces_replaced(self):
        result = sanitize_filename("ahmet yilmaz")
        assert " " not in result

    def test_empty_input(self):
        result = sanitize_filename("")
        assert result.startswith("person_")

    def test_max_length(self):
        long_name = "a" * 200
        assert len(sanitize_filename(long_name)) <= 100

    def test_special_chars_stripped(self):
        result = sanitize_filename("<script>alert(1)</script>")
        assert "<" not in result
        assert ">" not in result


class TestSafeSavePath:
    def test_valid_path(self, tmp_path):
        result = safe_save_path(tmp_path, "person.jpg")
        assert str(result).startswith(str(tmp_path))

    def test_traversal_raises(self, tmp_path):
        with pytest.raises(ValueError):
            safe_save_path(tmp_path, "../outside.jpg")

    def test_nested_traversal_raises(self, tmp_path):
        with pytest.raises(ValueError):
            safe_save_path(tmp_path, "subdir/../../outside.jpg")
