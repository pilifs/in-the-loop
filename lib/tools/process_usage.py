"""Wait for one Unix process and retain its own CPU and peak RSS accounting."""

import os
import signal
import time


def wait(process, seconds, *, process_group=False):
    deadline = time.monotonic() + seconds
    timed_out = False
    while True:
        pid, status, usage = os.wait4(process.pid, os.WNOHANG)
        if pid:
            process.returncode = os.waitstatus_to_exitcode(status)
            return timed_out, usage
        if time.monotonic() >= deadline and not timed_out:
            try:
                if process_group:
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    os.kill(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # The exit raced with the deadline; wait4 still owns the child's status.
            timed_out = True
        time.sleep(0.01)
