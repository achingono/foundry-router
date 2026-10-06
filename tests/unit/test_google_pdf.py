"""Finite PDF parser, preparation and immutable admission regressions."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import sys

import pytest
from google_pdf_fixtures import document, pdf
from pydantic import ValidationError
from pypdf import PdfWriter

from foundry_router.api.adapters.google_native import GoogleNativeAdapter
from foundry_router.api.google_pdf import (
    PdfPreparationError,
    PdfPreparer,
    PreparedGoogleMedia,
    PreparedPdf,
    decode_pdf,
)
from foundry_router.api.google_pdf_syntax import Tokens, inspect_pdf
from foundry_router.config import BackendConfig
from foundry_router.config.google_features import GoogleFeatureProfile


def part(raw: bytes) -> dict:
    return {
        "type": "input_file",
        "filename": "fixture.pdf",
        "file_data": "data:application/pdf;base64," + base64.b64encode(raw).decode(),
    }


def profile(**extra):
    return GoogleFeatureProfile(
        features=("inline_pdfs",),
        native_thinking_disabled=True,
        pdf_token_pricing=True,
        pdf_input_tokens_per_page=258,
        pdf_native_text_tokens_per_page=65536,
        **extra,
    )


@pytest.mark.parametrize("pages", [1, 2, 4])
def test_valid_standard_text_and_page_parent_backedges(pages):
    assert inspect_pdf(document(pages)) == pages


def test_content_operator_bound_applies_to_whole_document():
    assert inspect_pdf(document(4, content=b"BT /F1 12 Tf " + b"(x) Tj " * 509 + b"ET")) == 4
    with pytest.raises(ValueError):
        inspect_pdf(document(4, content=b"BT /F1 12 Tf " + b"(x) Tj " * 510 + b"ET"))


def test_ordinary_writer_blank_page():
    writer = PdfWriter()
    writer.pdf_header = b"%PDF-1.4"
    writer.add_blank_page(width=100, height=100)
    output = io.BytesIO()
    writer.write(output)
    assert inspect_pdf(output.getvalue()) == 1


def test_four_pages_share_verified_inherited_resources():
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 4 /Kids [5 0 R 6 0 R 7 0 R 8 0 R] /Resources 3 0 R /MediaBox [0 0 100 100] >>",
        b"<< /Font << /F1 4 0 R >> >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    objects.extend([b"<< /Type /Page /Parent 2 0 R >>"] * 4)
    assert inspect_pdf(pdf(objects)) == 4


@pytest.mark.parametrize(
    "parent",
    [
        b"/Resources << /XObject << /Im1 << /Type /XObject /Subtype /Image /Filter /FlateDecode >> >> >>",
        b"/CropBox [0 0 1000000 1000000]",
    ],
)
def test_overridden_parent_forbidden_resources_and_geometry_reject(parent, monkeypatch):
    raw = pdf(
        [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Count 1 /Kids [3 0 R] " + parent + b" >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /CropBox [0 0 100 100] /Resources <<>> >>",
        ]
    )
    monkeypatch.setattr(
        "pypdf.PdfReader", lambda *_a, **_k: pytest.fail("Forbidden parent reached dependency")
    )
    with pytest.raises(ValueError):
        inspect_pdf(raw)


@pytest.mark.parametrize(
    "operator",
    [
        b"BI /W 1 /H 1 ID X EI",
        b"/X Do",
        b"/X gs",
        b"q",
        b"/X BMC",
        b"1e99 Td",
        b"BT (x) Tj ET",
        b"BT BT ET",
        b"BT /F1 12 Tf (x) Tj",
        b"BT /F1 0 Tf ET",
        b"BT /F1 12 Tf [1 2] Tj ET",
        b"BT /F1 12 Tf 1.5 Tr ET",
    ],
)
def test_content_operators_and_bounds_rejected_before_dependency(operator, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Dependency reached before raw content validation")

    monkeypatch.setattr("pypdf.PdfReader", forbidden)
    with pytest.raises(ValueError):
        inspect_pdf(document(content=operator))


@pytest.mark.parametrize(
    "extra",
    [b"/Filter /FlateDecode ", b"/F (https://private.test/) ", b"/Type /ObjStm ", b"/Length 1 "],
)
def test_stream_dictionary_and_duplicate_length_rejected(extra):
    with pytest.raises(ValueError):
        inspect_pdf(document(extra=extra))


@pytest.mark.parametrize(
    "extra",
    [
        b"/UserUnit 999 ",
        b"/Annots [] ",
        b"/AA <<>> ",
        b"/MediaBox [0 0 100000 1] ",
        b"/Parent 3 0 R ",
    ],
)
def test_page_state_and_geometry_rejected(extra):
    with pytest.raises(ValueError):
        inspect_pdf(document(page_extra=extra))


@pytest.mark.parametrize(
    "fault", ["offset", "endstream", "length", "eof", "prefix", "object", "size", "encryption"]
)
def test_classic_raw_framing_faults_reject_before_dependency(fault, monkeypatch):
    raw = document()
    if fault == "offset":
        raw = raw.replace(b"0000000009", b"0000000010")
    elif fault == "endstream":
        raw = raw.replace(b"\nendstream", b"Xendstream")
    elif fault == "length":
        raw = raw.replace(b"/Length 28", b"/Length 29")
    elif fault == "eof":
        raw = raw[:-4]
    elif fault == "prefix":
        raw = b"X" + raw[1:]
    elif fault == "object":
        raw = raw.replace(b"3 0 obj", b"8 0 obj")
    elif fault == "size":
        raw = raw.replace(b"/Size 6", b"/Size 7")
    else:
        raw = pdf(
            [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [] /Count 0 >>"],
            trailer=b"/Encrypt 2 0 R ",
        )
    monkeypatch.setattr(
        "pypdf.PdfReader", lambda *_a, **_k: pytest.fail("Raw fault reached dependency")
    )
    with pytest.raises(ValueError):
        inspect_pdf(raw)


def test_unreachable_objects_and_page_cycles_rejected():
    for raw in (
        pdf([b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Count 1 /Kids [2 0 R] >>"]),
        pdf(
            [
                b"<< /Type /Catalog /Pages 2 0 R >>",
                b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] >>",
                b"<< /PrivateState (private) >>",
            ]
        ),
    ):
        with pytest.raises(ValueError):
            inspect_pdf(raw)


@pytest.mark.parametrize(
    "source",
    [
        b"<< /A 1 /A 2 >>",
        b"[" * 20,
        b"(x",
        b"<xz>",
        b"/A#20B",
        b"nan",
        b"1000001",
        b"[" + b"1 " * 257 + b"]",
    ],
)
def test_tokenizer_bounds(source):
    with pytest.raises(ValueError):
        Tokens(source).value()


def test_tokenizer_strings_numbers_arrays():
    assert Tokens(b"(a\\n\\101\\\r\nb)").value() == b"a\nAb"
    assert Tokens(b"<6162>").value() == b"ab"
    assert Tokens(b"[true false null 1.5]").value() == [True, False, None, 1.5]


@pytest.mark.parametrize("separator", [b"\r", b"\n", b"\r\n"])
def test_pdf_comments_cannot_hide_actions_filters_or_operators(separator, monkeypatch):
    monkeypatch.setattr(
        "pypdf.PdfReader", lambda *_a, **_k: pytest.fail("Forbidden raw field reached dependency")
    )
    for raw in (
        document(
            page_extra=b"%hidden"
            + separator
            + b"/AA << /O << /S /URI /URI (https://private.test/) >> >>\n"
        ),
        document(extra=b"%hidden" + separator + b"/Filter /FlateDecode\n"),
        document(content=b"%hidden" + separator + b"/X Do\n"),
    ):
        with pytest.raises(ValueError):
            inspect_pdf(raw)


def test_owned_preparation_admission_and_unchanged_mapping():
    p = part(document())
    body = {
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "before"},
                    p,
                    {"type": "input_text", "text": "after"},
                ],
            }
        ]
    }
    prepared = PreparedGoogleMedia(
        (
            PreparedPdf(
                (0, 1), hashlib.sha256(p["file_data"].encode()).hexdigest(), len(document()), 1
            ),
        )
    )
    adapter = GoogleNativeAdapter(profile=profile())
    assert adapter.check_request("responses", body) is not None
    assert adapter.check_request("responses", body, prepared_media=prepared) is None
    result = adapter.build_upstream_body(
        "responses", body, deployment="unused", default_output_tokens=5, prepared_media=prepared
    )
    assert result["contents"][0]["parts"] == [
        {"text": "before"},
        {"inlineData": {"mimeType": "application/pdf", "data": p["file_data"].split(",", 1)[1]}},
        {"text": "after"},
    ]
    p["file_data"] += "A"
    assert adapter.check_request("responses", body, prepared_media=prepared) is not None


@pytest.mark.parametrize(
    "patch",
    [
        {"file_url": "https://private.test/"},
        {"filename": "../x.pdf"},
        {"file_data": "data:application/pdf;base64,%%%"},
        {"file_data": "data:image/png;base64,AA=="},
        {"filename": "/private.pdf"},
    ],
)
def test_inline_encoding_egress_and_path_rejections(patch):
    with pytest.raises(PdfPreparationError):
        decode_pdf({**part(document()), **patch})


def test_profile_surface_and_missing_ceilings():
    with pytest.raises(ValidationError):
        GoogleFeatureProfile(features=("inline_pdfs",))
    with pytest.raises(ValidationError):
        BackendConfig(
            provider="google_ai_studio",
            endpoint="https://synthetic.test",
            credential="synthetic",
            deployment="synthetic",
            google_features=profile(),
        )


async def test_preparer_slot_saturation_release_and_metadata(monkeypatch):
    preparer = PdfPreparer()
    monkeypatch.setattr("foundry_router.api.google_pdf.pdf_worker_available", lambda: True)

    async def inspect(raw, *, deadline):
        _ = raw, deadline
        return 1

    monkeypatch.setattr(preparer, "inspect", inspect)
    preparer.active = 2
    body = {"input": [{"role": "user", "content": [part(document())]}]}
    with pytest.raises(PdfPreparationError, match="capacity"):
        await preparer.prepare(body, deadline=1)
    preparer.active = 0
    result = await preparer.prepare(body, deadline=1)
    assert result.pdfs[0].pages == 1 and preparer.active == 0
    body["input"][0]["content"][0]["file_data"] = "invalid"
    with pytest.raises(PdfPreparationError):
        await preparer.prepare(body, deadline=1)
    assert preparer.active == 0


@pytest.mark.skipif(sys.platform != "linux", reason="Enforced PDF RLIMIT_AS requires Linux")
async def test_real_isolated_worker_valid_and_invalid():
    preparer = PdfPreparer()
    deadline = asyncio.get_running_loop().time() + 5
    assert await preparer.inspect(document(), deadline=deadline) == 1
    with pytest.raises(PdfPreparationError):
        await preparer.inspect(b"invalid", deadline=deadline)


@pytest.mark.parametrize(
    "scenario", ["valid", "invalid", "overflow", "metadata", "stall", "cancel"]
)
async def test_child_output_deadline_cancellation_and_reap(monkeypatch, scenario):
    class Input:
        def write(self, data):
            self.data = data

        async def drain(self):
            pass

        def close(self):
            pass

        async def wait_closed(self):
            pass

    class Output:
        def __init__(self):
            self.sent = False

        async def read(self, size):
            if scenario in {"stall", "cancel"}:
                await asyncio.sleep(10)
            if self.sent:
                return b""
            self.sent = True
            raw = (
                b"x" * 1025
                if scenario == "overflow"
                else b'{"pages":1,"bytes":5}'
                if scenario != "metadata"
                else b'{"pages":true,"bytes":5}'
            )
            return raw[:size]

    class Child:
        def __init__(self):
            self.stdin = Input()
            self.stdout = Output()
            self.returncode = None
            self.killed = False
            self.reaped = False

        async def wait(self):
            self.reaped = True
            self.returncode = 1 if scenario == "invalid" else 0
            return self.returncode

        def kill(self):
            self.killed = True

    child = Child()

    async def spawn(*args, **kwargs):
        assert "-I" in args and kwargs["env"]["PATH"] == ""
        assert kwargs["stderr"] == asyncio.subprocess.DEVNULL
        return child

    monkeypatch.setattr("asyncio.create_subprocess_exec", spawn)
    preparer = PdfPreparer()
    deadline = asyncio.get_running_loop().time() + (0.02 if scenario == "stall" else 5)
    if scenario == "valid":
        assert await preparer.inspect(b"12345", deadline=deadline) == 1
    elif scenario == "cancel":
        task = asyncio.create_task(preparer.inspect(b"12345", deadline=deadline))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        with pytest.raises(PdfPreparationError):
            await preparer.inspect(b"12345", deadline=deadline)
    assert child.reaped
    if scenario in {"overflow", "stall", "cancel"}:
        assert child.killed


def test_worker_entrypoint_limits_and_safe_metadata(monkeypatch, capsys):
    import resource

    from foundry_router.api import google_pdf_worker

    calls = []
    monkeypatch.setattr(resource, "setrlimit", lambda key, value: calls.append((key, value)))

    class Input:
        buffer = io.BytesIO(document())

    monkeypatch.setattr(google_pdf_worker.sys, "stdin", Input())
    assert google_pdf_worker.main() == 0
    assert len(calls) == 4 and '"pages":1' in capsys.readouterr().out
    Input.buffer = io.BytesIO(b"private invalid document")
    assert google_pdf_worker.main() == 1 and capsys.readouterr().out == ""


async def test_cancellation_during_spawn_retains_child_until_reaped(monkeypatch):
    started = asyncio.Event()
    released = asyncio.Event()

    class Child:
        returncode = None
        stdin = None
        stdout = None
        killed = False
        reaped = False

        def kill(self):
            self.killed = True

        async def wait(self):
            self.returncode = -9
            self.reaped = True
            return -9

    child = Child()

    async def spawn(*_args, **_kwargs):
        started.set()
        await released.wait()
        return child

    monkeypatch.setattr("asyncio.create_subprocess_exec", spawn)
    task = asyncio.create_task(
        PdfPreparer().inspect(b"fixture", deadline=asyncio.get_running_loop().time() + 5)
    )
    await started.wait()
    task.cancel()
    released.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert child.killed and child.reaped


async def test_preparation_snapshot_cannot_bind_uninspected_mutation(monkeypatch):
    preparer = PdfPreparer()
    monkeypatch.setattr("foundry_router.api.google_pdf.pdf_worker_available", lambda: True)
    body = {"input": [{"role": "user", "content": [part(document())]}]}

    async def inspect(_raw, *, deadline):
        _ = deadline
        body["input"][0]["content"][0]["file_data"] = part(document(4))["file_data"]
        return 1

    monkeypatch.setattr(preparer, "inspect", inspect)
    facts = await preparer.prepare(body, deadline=1)
    with pytest.raises(ValueError):
        facts.validate(body, profile())


async def test_repeated_cancellation_releases_promptly_and_tracks_orphan(monkeypatch):
    from foundry_router.api import google_pdf as pdf_module

    released = asyncio.Event()
    waiting = asyncio.Event()

    class Child:
        stdin = None
        stdout = None
        returncode = None
        reaped = False
        killed = False

        def kill(self):
            self.killed = True

        async def wait(self):
            waiting.set()
            await released.wait()
            self.returncode = -9
            self.reaped = True
            return -9

    child = Child()

    async def spawn(*_a, **_k):
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    base_orphans = pdf_module.pdf_orphaned_children()
    task = asyncio.create_task(
        PdfPreparer().inspect(b"x", deadline=asyncio.get_running_loop().time() + 5)
    )
    await waiting.wait()
    for _ in range(3):
        task.cancel()
        await asyncio.sleep(0)
    # Bounded cleanup never suppresses cancellation for a stalled reap.
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 2)
    assert child.killed
    assert pdf_module.pdf_orphaned_children() == base_orphans + 1
    released.set()
    async with asyncio.timeout(2):
        while pdf_module.pdf_orphaned_children() > base_orphans:  # noqa: ASYNC110
            await asyncio.sleep(0.01)
    assert child.reaped


async def test_real_overflow_child_closes_pipe_and_reaps(monkeypatch):
    original = asyncio.create_subprocess_exec
    children = []

    async def spawn(*_args, **kwargs):
        child = await original(
            sys.executable,
            "-c",
            "import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write(b'x'*300000); sys.stdout.flush()",
            **kwargs,
        )
        children.append(child)
        return child

    monkeypatch.setattr("asyncio.create_subprocess_exec", spawn)
    with pytest.raises(PdfPreparationError):
        await PdfPreparer().inspect(b"x", deadline=asyncio.get_running_loop().time() + 5)
    await asyncio.sleep(0)
    assert children[0].returncode is not None
    assert children[0].stdout._transport.is_closing()


@pytest.mark.parametrize("available", [True, False])
async def test_readiness_selftest_cached_and_infrastructure_failure(monkeypatch, available):
    preparer = PdfPreparer()
    monkeypatch.setattr("foundry_router.api.google_pdf.pdf_worker_available", lambda: True)
    calls = []

    async def inspect(raw, *, deadline):
        _ = deadline
        calls.append(raw)
        if not available:
            raise PdfPreparationError(503, "unavailable")
        return 1

    monkeypatch.setattr(preparer, "inspect", inspect)
    assert await preparer.ready() is available
    assert await preparer.ready() is available
    # Success stays cached; transient failure retries so recovery is observed.
    assert len(calls) == (1 if available else 2)


def test_pinned_worker_version_readiness(monkeypatch):
    from foundry_router.api.google_pdf import pdf_worker_available

    monkeypatch.setattr("foundry_router.api.google_pdf.sys.platform", "linux")
    monkeypatch.setattr(
        "foundry_router.api.google_pdf.importlib.metadata.version", lambda _name: "0.0.0"
    )
    assert not pdf_worker_available()


async def test_spawn_failure_is_safe_infrastructure_failure(monkeypatch):
    async def spawn(*_a, **_k):
        raise FileNotFoundError("PRIVATE_PATH")

    monkeypatch.setattr("asyncio.create_subprocess_exec", spawn)
    monkeypatch.setattr("foundry_router.api.google_pdf.pdf_worker_available", lambda: True)
    preparer = PdfPreparer()
    with pytest.raises(PdfPreparationError) as failure:
        await preparer.inspect(b"x", deadline=asyncio.get_running_loop().time() + 5)
    assert failure.value.status_code == 503 and "PRIVATE_PATH" not in str(failure.value)
    assert await preparer.ready() is False and preparer.active == 0


async def test_readiness_shares_two_worker_slots_and_retries_saturation(monkeypatch):
    preparer = PdfPreparer()
    monkeypatch.setattr("foundry_router.api.google_pdf.pdf_worker_available", lambda: True)
    preparer.active = 2
    assert await preparer.ready() is False and preparer.probe is None
    preparer.active = 0

    async def inspect(_raw, *, deadline):
        _ = deadline
        assert preparer.active == 1
        return 1

    monkeypatch.setattr(preparer, "inspect", inspect)
    assert await preparer.ready() is True and preparer.active == 0


@pytest.mark.parametrize(
    ("sizes", "counts", "valid", "inspections"),
    [
        ([65536, 65536], [1, 1], True, 2),
        ([32768] * 4, [1] * 4, True, 4),
        ([65536, 65536, 128], [1] * 3, False, 2),
        ([128, 128], [3, 2], False, 2),
        ([128] * 5, [1] * 5, False, 0),
    ],
)
async def test_preparation_aggregate_limits_before_reservation(
    monkeypatch, sizes, counts, valid, inspections
):
    preparer = PdfPreparer()
    monkeypatch.setattr("foundry_router.api.google_pdf.pdf_worker_available", lambda: True)
    visited = []

    async def inspect(raw, *, deadline):
        _ = deadline
        visited.append(len(raw))
        return counts[len(visited) - 1]

    monkeypatch.setattr(preparer, "inspect", inspect)
    body = {"input": [{"role": "user", "content": [part(b"x" * size) for size in sizes]}]}
    if valid:
        result = await preparer.prepare(body, deadline=1)
        assert sum(entry.decoded_bytes for entry in result.pdfs) == sum(sizes)
        result.validate(body, profile())
    else:
        with pytest.raises(PdfPreparationError):
            await preparer.prepare(body, deadline=1)
    assert len(visited) == inspections and preparer.active == 0


@pytest.mark.parametrize(
    "caps",
    [{"max_pdfs": 1}, {"max_pdf_bytes": 128}, {"max_total_pdf_bytes": 512}, {"max_pdf_pages": 1}],
)
def test_owned_facts_enforce_lower_candidate_caps(caps):
    raw = document()
    body = {"input": [{"role": "user", "content": [part(raw), part(raw)]}]}
    entries = tuple(
        PreparedPdf((0, index), hashlib.sha256(item["file_data"].encode()).hexdigest(), len(raw), 1)
        for index, item in enumerate(body["input"][0]["content"])
    )
    facts = PreparedGoogleMedia(entries)
    assert (
        GoogleNativeAdapter(profile=profile()).check_request(
            "responses", body, prepared_media=facts
        )
        is None
    )
    assert (
        GoogleNativeAdapter(profile=profile(**caps)).check_request(
            "responses", body, prepared_media=facts
        )
        is not None
    )
