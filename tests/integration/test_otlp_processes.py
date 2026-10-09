"""Real independent process exports to a central local OTLP receiver."""

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest

WORKER = """
import asyncio
from types import SimpleNamespace
from foundry_router.metrics.otlp import ConfinedMetricExporter, OtlpMetricsStore

async def main():
    settings = SimpleNamespace(models={"logical":SimpleNamespace(backends={"a":1})}, backends={"a":None}, telemetry_series_budget=2048, telemetry_service_name="synthetic", telemetry_replica_id="replica-"+__import__("sys").argv[2], telemetry_revision_id="test", telemetry_interval_seconds=5, telemetry_timeout_seconds=1, telemetry_endpoint=__import__("sys").argv[1], telemetry_authorization=None)
    exporter=ConfinedMetricExporter(settings.telemetry_endpoint,authorization="Bearer synthetic",timeout=1)
    store=OtlpMetricsStore(settings,exporter=exporter)
    count=int(__import__("sys").argv[2])
    for i in range(count):
        await store.observe_request(model="logical",backend="a",status_code=200,latency_seconds=0.2,estimated_cost_usd=0.5)
        await store.observe_combination_exclusion(backend="a",operation="responses",stream="nonstream",cleared=False)
    deadline=__import__("time").monotonic()+7
    while exporter.state!="acknowledged":
        assert __import__("time").monotonic()<deadline
        await asyncio.sleep(0.05)
    store._provider.force_flush(timeout_millis=1000)
    await store.shutdown()
    assert exporter.state=="acknowledged"
asyncio.run(main())
"""


def test_two_workers_restart_and_duplicate_cumulative_snapshots():
    captured = []
    lock = threading.Lock()

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            assert self.path == "/v1/metrics"
            assert self.headers["authorization"] == "Bearer synthetic"
            message = ExportMetricsServiceRequest()
            message.ParseFromString(self.rfile.read(int(self.headers["content-length"])))
            with lock:
                captured.append(message)
            self.send_response(200)
            self.send_header("content-length", "0")
            self.end_headers()

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/v1/metrics"
    try:
        workers = [
            subprocess.Popen(
                [sys.executable, "-c", WORKER, endpoint, str(count)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for count in (2, 3)
        ]
        for process in workers:
            stdout, stderr = process.communicate(timeout=10)
            assert process.returncode == 0, (stdout, stderr)
        restart = subprocess.run(
            [sys.executable, "-c", WORKER, endpoint, "4"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert restart.returncode == 0, restart.stderr
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    identities = set()
    latest = {}
    # Deliberately reverse/repeat deliveries. Highest timestamp per cumulative series wins;
    # first lifetime sample contributes its full value. State is central collector semantics.
    for message in [*reversed(captured), *captured]:
        for resource in message.resource_metrics:
            attrs = {
                attribute.key: attribute.value.string_value
                for attribute in resource.resource.attributes
            }
            instance = attrs["service.instance.id"]
            identities.add(instance)
            for scope in resource.scope_metrics:
                for metric in scope.metrics:
                    field = metric.WhichOneof("data")
                    for point in getattr(metric, field).data_points:
                        labels = tuple(
                            sorted((a.key, a.value.string_value) for a in point.attributes)
                        )
                        key = instance, metric.name, labels, point.start_time_unix_nano
                        if key not in latest or point.time_unix_nano > latest[key][0]:
                            latest[key] = point.time_unix_nano, point
    assert len(identities) == 3
    sums = {}
    histogram_count, histogram_sum = 0, 0
    for (_instance, name, _labels, _start), (_end, point) in latest.items():
        if name == "foundry_router_latency_seconds":
            histogram_count += point.count
            histogram_sum += point.sum
            assert sum(point.bucket_counts) == point.count
            assert point.bucket_counts[2] == point.count
        else:
            sums[name] = sums.get(name, 0) + getattr(point, point.WhichOneof("value"))
    assert sums["foundry_router_requests_total"] == 9
    assert sums["foundry_router_estimated_cost_usd_total"] == 4.5
    assert sums["combination_exclusion_entries_total"] == 9
    assert histogram_count == 9 and abs(histogram_sum - 1.8) < 1e-9
    assert len(captured) >= 6
    assert "synthetic" not in json.dumps(sums)
