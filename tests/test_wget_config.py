#!/usr/bin/env python3
"""Exercise the tracked Wget policy against an inert loopback download server."""

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[1]
WGET = shutil.which("wget")
PAYLOAD = b"# inert download; never execute\n"


class DownloadHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_HEAD(self):
        self.respond(send_body=False)

    def do_GET(self):
        self.respond(send_body=True)

    def respond(self, send_body):
        if self.path == "/download":
            self.send_response(302)
            self.send_header("Location", "/.bashrc")
            self.end_headers()
            return
        if self.path not in ("/.bashrc", "/existing.txt"):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(PAYLOAD)))
        self.send_header("Last-Modified", "Wed, 01 Jan 2031 00:00:00 GMT")
        self.end_headers()
        if send_body:
            self.wfile.write(PAYLOAD)


@unittest.skipUnless(WGET, "Requires Wget; downloads use loopback and a temporary HOME")
class WgetConfigTests(unittest.TestCase):
    def test_downloads_preserve_existing_files_and_ignore_redirect_filenames(self):
        with tempfile.TemporaryDirectory(prefix="wget security ") as directory:
            home = Path(directory).resolve()
            original = b"original local content\n"
            for name in (".bashrc", "existing.txt"):
                (home / name).write_bytes(original)
                os.utime(home / name, (946684800, 946684800))
            server = HTTPServer(("127.0.0.1", 0), DownloadHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                env = {
                    "HOME": str(home), "PATH": "/usr/bin:/bin", "LC_ALL": "C",
                    "WGETRC": str(ROOT / ".config/wget/wgetrc"),
                }
                for path in ("download", "existing.txt"):
                    with self.subTest(path=path):
                        result = subprocess.run(
                            [WGET, "--no-proxy", "--hsts-file=" + str(home / "hsts"),
                             f"http://127.0.0.1:{server.server_port}/{path}"],
                            cwd=home, env=env, capture_output=True, timeout=20,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr.decode())
                        self.assertEqual((home / ".bashrc").read_bytes(), original)
                        self.assertEqual((home / "existing.txt").read_bytes(), original)
                self.assertEqual((home / "download").read_bytes(), PAYLOAD)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
