# mp_parser/proxy_manager.py
import time
import random
from typing import Dict, List, Optional, Iterable
from .config import PROXY_POOL, MAX_PROXY_FAILS_BEFORE_COOLDOWN, PROXY_COOLDOWN_SEC

class ProxyState:
    __slots__ = ("name", "server", "username", "password", "fails", "successes", "cooldown_until", "last_fail_ts")

    def __init__(self, p: Dict):
        self.name: str = p.get("name") or "NONAME"
        self.server: str = p.get("server") or ""
        self.username: Optional[str] = p.get("username")
        self.password: Optional[str] = p.get("password")
        self.fails: int = 0
        self.successes: int = 0
        self.cooldown_until: float = 0.0
        self.last_fail_ts: float = 0.0

    def to_proxy_dict(self) -> Dict:
        return {"name": self.name, "server": self.server, "username": self.username, "password": self.password}

    def is_on_cooldown(self, now: float) -> bool:
        return now < self.cooldown_until

class ProxyManager:
    def __init__(self, pool: List[Dict]):
        self._states: Dict[str, ProxyState] = {}
        for p in pool:
            st = ProxyState(p)
            if st.name not in self._states:
                self._states[st.name] = st

    def choose_proxy(self, exclude: Optional[Iterable[str]] = None) -> Optional[Dict]:
        if not self._states:
            return None
        ex = set(exclude or [])
        now = time.time()
        # Кандидаты: не на кулдауне и не в exclude
        candidates = [s for s in self._states.values() if (not s.is_on_cooldown(now)) and (s.name not in ex)]
        if not candidates:
            # Всё в кулдауне — берём с минимальным cooldown_until из не-exclude
            fallback = [s for s in self._states.values() if s.name not in ex] or list(self._states.values())
            s = min(fallback, key=lambda x: x.cooldown_until)
            return s.to_proxy_dict()
        # Сортируем по минимальным fails, потом по успехам (больше — лучше), рандом при равенстве
        candidates.sort(key=lambda s: (s.fails, -s.successes, random.random()))
        return candidates[0].to_proxy_dict()

    def report_success(self, name: Optional[str]) -> None:
        if not name or name not in self._states:
            return
        st = self._states[name]
        st.successes += 1
        st.fails = 0
        st.cooldown_until = 0.0

    def report_failure(self, name: Optional[str]) -> None:
        if not name or name not in self._states:
            return
        st = self._states[name]
        st.fails += 1
        st.last_fail_ts = time.time()
        # После N подряд неудач — охлаждение
        if st.fails >= MAX_PROXY_FAILS_BEFORE_COOLDOWN:
            st.cooldown_until = st.last_fail_ts + PROXY_COOLDOWN_SEC
            # не обнуляем полностью fails — пусть остаётся инерция
            # можно сбросить до 0 или 1 по желанию:
            # st.fails = 0

    def snapshot(self) -> List[Dict]:
        now = time.time()
        out = []
        for s in self._states.values():
            out.append({
                "name": s.name, "fails": s.fails, "successes": s.successes,
                "cooldown_sec_left": max(0, int(s.cooldown_until - now))
            })
        return out

# Singleton
proxy_manager = ProxyManager(PROXY_POOL)
