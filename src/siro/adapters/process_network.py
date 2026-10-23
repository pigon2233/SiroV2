"""Opt-in, read-only attribution of sockets to an owned process group (CP-O01).

Linux only, from /proc, unprivileged: a socket is attributed when a process of the group
holds it at sampling time. Sampling cannot see a connection that opened and closed between
two samples, so the result is `sampled`, never a complete audit. No TLS decryption, no
packet capture, no privilege escalation; other platforms report `unsupported`.
"""

from __future__ import annotations

import ipaddress
import os
import socket
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

_PROC = Path("/proc")
_TABLES = (("tcp", False), ("tcp6", True), ("udp", False), ("udp6", True))
_TCP_STATES = {"01": "established", "02": "syn_sent", "06": "time_wait", "0A": "listen"}


@dataclass(frozen=True, slots=True)
class Capability:
    status: str  # "sampled" | "unsupported"
    method: str
    reason: str = ""


@dataclass(frozen=True, slots=True)
class Connection:
    pid: int
    protocol: str
    remote: str
    port: int
    state: str


def probe_capability(proc: Path = _PROC) -> Capability:
    if not sys.platform.startswith("linux"):
        return Capability("unsupported", "none", f"no unprivileged method on {sys.platform}")
    if not (proc / "net" / "tcp").is_file():
        return Capability("unsupported", "none", "/proc/net unavailable")
    return Capability("sampled", "proc_fd_socket_inode")


def _addr(hex_ip: str, v6: bool) -> str:
    raw = bytes.fromhex(hex_ip)
    if v6:
        words = struct.unpack("<4I", raw)
        return str(ipaddress.IPv6Address(struct.pack(">4I", *words)))
    return socket.inet_ntoa(raw[::-1])


def _socket_table(proc: Path) -> dict[str, tuple[str, str, int, str]]:
    table: dict[str, tuple[str, str, int, str]] = {}
    for name, v6 in _TABLES:
        try:
            lines = (proc / "net" / name).read_text().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            f = line.split()
            if len(f) < 10:
                continue
            ip, port = f[2].split(":")
            state = _TCP_STATES.get(f[3], f[3]) if name.startswith("tcp") else "datagram"
            table[f[9]] = (name.rstrip("6"), _addr(ip, v6), int(port, 16), state)
    return table


def sample_group(pgid: int, proc: Path = _PROC) -> list[Connection]:
    """Sockets with a remote endpoint held right now by processes of `pgid`."""
    table = _socket_table(proc)
    found: list[Connection] = []
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            pid = int(entry.name)
            if os.getpgid(pid) != pgid:
                continue
            for fd in (entry / "fd").iterdir():
                target = os.readlink(fd)
                if target.startswith("socket:["):
                    hit = table.get(target[8:-1])
                    if hit and hit[3] != "listen" and hit[2] != 0:
                        found.append(Connection(pid, hit[0], hit[1], hit[2], hit[3]))
        except (OSError, ProcessLookupError):
            continue  # process or fd vanished while sampling
    return found
