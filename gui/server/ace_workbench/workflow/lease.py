"""One workbench owns a project at a time; OS locks are released after crashes."""

import os
from pathlib import Path


class ProjectLease:
    def __init__(self, path: Path):
        self.stream = path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt

                self.stream.seek(0)
                self.stream.write(b"0")
                self.stream.flush()
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.stream.close()
            raise ValueError(
                "This project is already open in another workbench process. Use that session or close it first."
            ) from exc

    def close(self):
        self.stream.close()
