"""
detection/log_throttle.py birim testleri.
"""
import time
import pytest
from detection.log_throttle import LogThrottle


class TestLogThrottle:
    def test_first_call_allowed(self):
        t = LogThrottle(cooldown_seconds=10)
        assert t.should_log("ahmet") is True

    def test_second_call_blocked(self):
        t = LogThrottle(cooldown_seconds=10)
        t.should_log("ahmet")
        assert t.should_log("ahmet") is False

    def test_different_persons_independent(self):
        t = LogThrottle(cooldown_seconds=10)
        assert t.should_log("ahmet") is True
        assert t.should_log("mehmet") is True

    def test_allowed_after_cooldown(self):
        t = LogThrottle(cooldown_seconds=0)  # sıfır saniye cooldown
        t.should_log("ahmet")
        time.sleep(0.01)
        assert t.should_log("ahmet") is True

    def test_reset_person(self):
        t = LogThrottle(cooldown_seconds=100)
        t.should_log("ahmet")
        t.reset("ahmet")
        assert t.should_log("ahmet") is True

    def test_reset_all(self):
        t = LogThrottle(cooldown_seconds=100)
        t.should_log("ahmet")
        t.should_log("mehmet")
        t.reset_all()
        assert t.should_log("ahmet") is True
        assert t.should_log("mehmet") is True
