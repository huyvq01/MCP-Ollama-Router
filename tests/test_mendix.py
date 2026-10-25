import asyncio
import json
import uuid
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.settings import Settings
from app.services.mendix import MendixService
from app.services.workspace import Workspace


@pytest.fixture
def service(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    project = project_root / "App.mpr"
    project.write_bytes(b"model")
    mx = tmp_path / "mx.exe"
    mx.write_bytes(b"fake host tool")
    root = tmp_path / "router"
    root.mkdir()
    config = Settings(_env_file=None, mendix_project=project, mendix_mx_executable=mx)
    router = Mock()
    router.chat = AsyncMock(return_value="Chưa đủ bằng chứng kết luận lỗi.")
    router.metrics.return_value = {"finish_reason": "stop", "model": "test"}
    return MendixService(config, Workspace(root), router)


def seed(service, large=False):
    job = {
        "id": uuid.uuid4().hex,
        "status": "completed",
        "modules": ["AMS"],
        "unit_types": ["Microflows$Microflow"],
        "project": str(service.project()),
        "fingerprint": service.fingerprint(),
    }
    service._save("exports", job)
    output = service.state / "input.json"
    unit_id = str(uuid.uuid4())
    output.write_text(
        json.dumps(
            {
                "units": [
                    {
                        "$ID": unit_id,
                        "$Type": "Microflows$Microflow",
                        "$QualifiedName": "AMS.Test",
                        "documentation": "evidence " * (400 if large else 1),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    job["counts"] = service._index(job, output)
    service._save("exports", job)
    return job["id"], unit_id


def test_index_pagination_bounded_evidence_and_read_only(service):
    export_id, unit_id = seed(service, large=True)
    assert service.list_units(export_id, "test")["total"] == 1
    assert service.list_units(export_id, "' OR 1=1 --")["total"] == 0
    chunk = service.read_unit(export_id, unit_id)
    assert len(chunk["content"].encode()) <= 1400
    assert chunk["next_chunk"] == 1
    assert "exported unit JSON" in chunk["evidence"]
    with pytest.raises(ValueError):
        service.read_unit(export_id, unit_id, -1)
    with pytest.raises(ValueError):
        service.export_status("../../other")
    assert sorted(p.name for p in service.project().parent.iterdir()) == ["App.mpr"]


async def test_resumable_report_owner_busy_and_truncation(service):
    export_id, unit_id = seed(service, large=True)
    report_id = service.start_report(export_id, unit_id, "alice")["report_id"]
    service.router.chat.side_effect = RuntimeError("Router is busy")
    status = await service.report_step(report_id, "alice")
    assert status["status"] == "retry_required" and status["processed"] == 0
    service.router.chat.side_effect = None
    service.router.metrics.return_value = {"finish_reason": "length"}
    status = await service.report_step(report_id, "alice")
    assert status["processed"] == 1
    assert "warning" in status["results"][0]
    restarted = MendixService(service.config, service.workspace, service.router)
    with pytest.raises(PermissionError):
        restarted.report_status(report_id, "bob")
    while status["status"] != "completed":
        status = await restarted.report_step(report_id, "alice")
    assert status["processed"] == status["total"]
    assert service.router.chat.call_args.kwargs["model"] == service.config.report_model


async def test_model_change_blocks_report(service):
    export_id, unit_id = seed(service)
    report_id = service.start_report(export_id, unit_id, "alice")["report_id"]
    contents = service.project().parent / "mprcontents"
    contents.mkdir()
    (contents / "new.mxunit").write_bytes(b"saved model changed")
    with pytest.raises(ValueError, match="changed"):
        await service.report_step(report_id, "alice")
    service.router.chat.assert_not_called()


def test_source_confinement_and_listing(service):
    root = service.project().parent
    actions = root / "javasource" / "ams" / "actions"
    actions.mkdir(parents=True)
    (actions / "Hello.java").write_text("class Hello {}", encoding="utf-8")
    (root / "firebase-adminsdk.json").write_text('{"private_key":"never read"}')
    node = actions / "node_modules"
    node.mkdir()
    (node / "Skip.java").write_text("never read")
    assert service.list_sources()["files"] == ["javasource/ams/actions/Hello.java"]
    assert "class Hello" in str(
        service.read_source("javasource/ams/actions/Hello.java")
    )
    for path in (
        "../outside.java",
        "firebase-adminsdk.json",
        "App.mpr",
        "javasource/ams/actions/node_modules/Skip.java",
    ):
        with pytest.raises(ValueError):
            service.read_source(path)


async def test_background_export_fixed_arguments_and_duplicate_block(
    service, monkeypatch
):
    started = asyncio.Event()
    finish = asyncio.Event()
    calls = []

    async def spawn(*args, **kwargs):
        calls.append(args)
        output = args[args.index("--output-file") + 1]
        with open(output, "w", encoding="utf-8") as stream:
            json.dump({"units": []}, stream)
        process = Mock(returncode=None)

        async def wait():
            started.set()
            await finish.wait()
            process.returncode = 0
            return 0

        process.wait = wait
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    with pytest.raises(ValueError):
        await service.start_export("AMS; evil", "Microflows$Microflow")
    job = await service.start_export("AMS", "Microflows$Microflow")
    await started.wait()
    with pytest.raises(RuntimeError, match="already running"):
        await service.start_export("AMS", "Microflows$Microflow")
    finish.set()
    await service.tasks[job["export_id"]]
    assert service.export_status(job["export_id"])["status"] == "completed"
    assert calls[0][1:4] == ("dump-mpr", "--module-names", "AMS")
    assert not list((service.state / "exports").glob("*.raw.json"))


async def test_export_failure_and_restart_status(service, monkeypatch):
    spawn = AsyncMock(return_value=Mock(returncode=4, wait=AsyncMock(return_value=4)))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    job = await service.start_export("AMS", "Microflows$Microflow")
    await service.tasks[job["export_id"]]
    status = service.export_status(job["export_id"])
    assert status["status"] == "failed" and "exited 4" in status["error"]
    job = {"id": uuid.uuid4().hex, "status": "indexing"}
    service._save("exports", job)
    assert service.export_status(job["id"])["status"] == "interrupted"
