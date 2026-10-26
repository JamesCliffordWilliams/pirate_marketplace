# utils/perf.py
# The Vault Campus Marketplace
# Created by James Williams - 10/26/26
# Measurement only (branch perf/listing-create-timing, not merged).
# With PM_TIMING=1: per-stage timings and a count of new DB connections,
# returned in a Server-Timing header, and S3 uploads go to listings/_perf/.

import os
import time

import psycopg2

ENABLED = os.getenv("PM_TIMING") == "1"
_state = {"connections": 0}

if ENABLED:
    _connect = psycopg2.connect

    def _counting_connect(*args, **kwargs):
        _state["connections"] += 1
        return _connect(*args, **kwargs)

    psycopg2.connect = _counting_connect


class StageTimer:
    def __init__(self):
        self.stages = []
        self.start = self.last = time.perf_counter()
        self.connections_at_start = _state["connections"]

    def mark(self, name):
        now = time.perf_counter()
        self.stages.append((name, (now - self.last) * 1000))
        self.last = now

    def header(self):
        parts = [f"{name};dur={ms:.1f}" for name, ms in self.stages]
        parts.append(f"total;dur={(time.perf_counter() - self.start) * 1000:.1f}")
        parts.append(f"db_connections;desc={_state['connections'] - self.connections_at_start}")
        return ", ".join(parts)


# PM_FAKE_S3=1: read the upload and return a fake URL, so the other stages can be timed without AWS
if ENABLED and os.getenv("PM_FAKE_S3") == "1":
    import uuid
    import utils.s3 as s3

    def _fake_upload(file, folder="uploads"):
        file.read()
        return f"http://127.0.0.1:5052/fake/{folder}/{uuid.uuid4().hex}"

    s3.upload_image_to_s3 = _fake_upload


def upload_folder(folder):
    return f"{folder}/_perf" if ENABLED else folder
