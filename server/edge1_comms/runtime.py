"""Runtime resource and abuse controls shared by IRC and NNTP."""

from __future__ import annotations

import socket
import socketserver
import threading
import time
from collections import defaultdict, deque

class TokenBucket:
    def __init__(self, rate: int, burst: int) -> None:
        self.rate=float(rate); self.capacity=float(burst); self.tokens=float(burst); self.updated=time.monotonic()
    def allow(self) -> bool:
        now=time.monotonic(); elapsed=max(0.0,now-self.updated); self.updated=now
        self.tokens=min(self.capacity,self.tokens+elapsed*self.rate)
        if self.tokens<1.0: return False
        self.tokens-=1.0; return True

class AuthThrottle:
    """Bound failed authentication attempts per peer across reconnects."""
    def __init__(self, failures_per_minute: int) -> None:
        self.limit=failures_per_minute; self._lock=threading.Lock(); self._failures: dict[str,deque[float]]=defaultdict(deque)
    def allowed(self, peer: str) -> bool:
        now=time.monotonic()
        with self._lock:
            items=self._failures[peer]
            while items and now-items[0]>=60.0: items.popleft()
            return len(items)<self.limit
    def failure(self, peer: str) -> None:
        now=time.monotonic()
        with self._lock:
            items=self._failures[peer]
            while items and now-items[0]>=60.0: items.popleft()
            items.append(now)
    def success(self, peer: str) -> None:
        with self._lock: self._failures.pop(peer,None)

class BoundedThreadingTCPServer(socketserver.ThreadingTCPServer):
    """Threading TCP server with total/per-peer connection limits and timeouts."""
    allow_reuse_address=True; daemon_threads=True
    def configure_runtime_limits(self, *, max_connections: int, max_connections_per_ip: int, idle_timeout_seconds: int) -> None:
        self._limit_lock=threading.Lock(); self._active_total=0; self._active_by_peer: dict[str,int]=defaultdict(int)
        self._max_connections=max_connections; self._max_connections_per_ip=max_connections_per_ip; self._idle_timeout_seconds=idle_timeout_seconds
    def process_request(self, request: socket.socket, client_address: tuple[str,int]) -> None:
        peer=str(client_address[0])
        with self._limit_lock:
            if self._active_total>=self._max_connections or self._active_by_peer[peer]>=self._max_connections_per_ip:
                request.close(); return
            self._active_total+=1; self._active_by_peer[peer]+=1
        try:
            request.settimeout(self._idle_timeout_seconds); super().process_request(request,client_address)
        except Exception:
            self._release_peer(peer); raise
    def process_request_thread(self, request: socket.socket, client_address: tuple[str,int]) -> None:
        peer=str(client_address[0])
        try: super().process_request_thread(request,client_address)
        finally: self._release_peer(peer)
    def _release_peer(self, peer: str) -> None:
        with self._limit_lock:
            self._active_total=max(0,self._active_total-1); current=self._active_by_peer.get(peer,0)
            if current<=1: self._active_by_peer.pop(peer,None)
            else: self._active_by_peer[peer]=current-1
    def connection_stats(self)->dict[str,int]:
        with self._limit_lock: return {'active':self._active_total,'peers':len(self._active_by_peer)}
