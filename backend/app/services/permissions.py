import os
from dataclasses import dataclass


@dataclass
class DirPermission:
    path: str
    exists: bool
    readable: bool
    writable: bool

    @property
    def ok(self) -> bool:
        return self.exists and self.readable and self.writable


def check_dir(path: str) -> DirPermission:
    exists = os.path.isdir(path)
    readable = exists and os.access(path, os.R_OK | os.X_OK)
    writable = exists and os.access(path, os.W_OK)
    return DirPermission(path=path, exists=exists, readable=readable, writable=writable)
