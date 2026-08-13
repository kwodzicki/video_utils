import logging
import subprocess
import threading
import queue


class FanOutProcess:
    def __init__(
        self,
        name: str,
        command: list[str],
        input_queue: queue.Queue | None = None,
        encoding: str = "utf-8",
    ):
        """
        Arguments:
            name (str): Name for the processing; using in logging
            command: List[str] or str for subprocess
            input_queue: queue.Queue instance for stdin messages
            encoding: encoding for stdin/stderr

        """

        self._log = logging.getLogger(__name__)

        self.name = name
        self.command = command
        self.input_queue = input_queue or queue.Queue(maxsize=32)
        self.encoding = encoding

        self.process = None
        self._stop_event = threading.Event()

        self._stdin_thread = None
        self._stderr_thread = None

    def log(self, lvl: int, fmt: str, *args):

        self._log.log(lvl, "%s - " + fmt, self.name, *args)

    def start(self):
        """Start the subprocess and worker threads."""

        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            bufsize=0,  # line-buffered
        )

        self._stdin_thread = threading.Thread(
            target=self._stdin_worker,
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._stderr_worker,
            daemon=True,
        )

        self._stdin_thread.start()
        self._stderr_thread.start()

    def stop(self):
        """Signal threads to stop and terminate process."""

        self._stop_event.set()

        if self.process is None:
            return

        try:
            self.process.stdin.close()
        except Exception:
            pass

        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.log(
                logging.WARNING,
                "Subprocess terminate failed; killing",
            )
            self.process.kill()

        self.process = None
        self.log(logging.DEBUG, 'Process stopped')

    def send(self, message: bytes) -> None:
        """Put a message into the queue."""

        if self.process is None:
            return

        self.input_queue.put(message)

    def _stdin_worker(self):
        """Continuously read from queue and write to subprocess stdin."""

        while not self._stop_event.is_set():
            try:
                message = self.input_queue.get(timeout=0.5)
            except queue.Empty:
                if self._process_exited():
                    self.log(
                        logging.WARNING,
                        "Process exited while waiting for input.",
                    )
                    break
                continue

            if message is None:
                # Sentinel to stop
                break

            if self._process_exited():
                self.log(
                    logging.WARNING,
                    "Process already exited. Dropping message.",
                )
                break

            try:
                if self.process.stdin:
                    self.process.stdin.write(message)
                    self.process.stdin.flush()
            except BrokenPipeError as e:
                self.log(
                    logging.ERROR,
                    "Broken pipe detected. Subprocess likely exited: %s",
                    e,
                )
                break
            except OSError as e:
                self.log(logging.ERROR, "Unexpected stdin write error: %s", e)
                break
            except Exception as e:
                logging.error("Generic stdin error: %s", e)
                break

        self.stop()
        self._drain_queue()

    def _stderr_worker(self):
        try:
            for line in self.process.stderr:
                if self._stop_event.is_set():
                    break
                self.log(
                    logging.ERROR,
                    "Issue with subprocess: %s",
                    line.rstrip(),
                )
        except Exception as e:
            self.log(logging.ERROR, "Error reading stderr: %s", e)

    def _process_exited(self):
        return self.process.poll() is not None

    def _drain_queue(self):
        """Clear remaining messages to avoid blocking producers."""
        try:
            while True:
                self.input_queue.get_nowait()
        except queue.Empty:
            pass

    def wait(self):
        if self.process:
            return self.process.wait()
        return None
