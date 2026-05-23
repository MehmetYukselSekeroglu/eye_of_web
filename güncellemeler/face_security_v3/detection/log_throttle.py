"""
Log ve bildirim throttle mekanizması.
Aynı kişi için belirli süre geçmeden tekrar log/bildirim üretmez.
"""
import time
from collections import defaultdict


class LogThrottle:
    def __init__(self, cooldown_seconds: int = 30):
        self.cooldown = cooldown_seconds
        self._last_seen: dict[str, float] = defaultdict(float)

    def should_log(self, person_id: str) -> bool:
        """
        Bu kişi için log üretilebilir mi?
        True dönüyorsa log yaz; False dönüyorsa atla.
        """
        now = time.time()
        if now - self._last_seen[person_id] >= self.cooldown:
            self._last_seen[person_id] = now
            return True
        return False

    def reset(self, person_id: str) -> None:
        """Belirli bir kişinin throttle sayacını sıfırlar."""
        self._last_seen.pop(person_id, None)

    def reset_all(self) -> None:
        """Tüm throttle sayaçlarını sıfırlar."""
        self._last_seen.clear()
