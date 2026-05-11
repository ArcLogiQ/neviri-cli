"""Phase-1 E2E happy-path workflow test (Story 5.4).

Walks the full provisioning flow a user would script through the CLI:

    1. neviri network create     →  POST /network/networks
    2. neviri subnet create      →  POST /network/subnets
    3. neviri vm create          →  POST /compute/servers
    4. neviri volume create      →  POST /block-storage/volumes
    5. neviri volume attach      →  POST /block-storage/volumes/{id}/attach
    6. neviri floating-ip alloc  →  POST /network/floating-ips
    7. neviri floating-ip assoc  →  PUT  /network/floating-ips/{id}/associate

And the inverse cleanup sequence.

The "SSH into the VM succeeds" requirement from Story 5's draft AC is not
testable at this layer (it requires real OpenStack + a real VM). The check
here is that every CLI step issues the right HTTP call against the right URL
with the right body. Confidence in the wiring; the cloud part is for staging
E2E.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from neviri_cli.app import app
from neviri_cli.auth import store_token

BACKEND = "http://localhost:8000"


@pytest.fixture
def logged_in(isolated_home: Path) -> None:
    store_token("default", "test-token")


@respx.mock
def test_full_provision_workflow(logged_in: None, runner: CliRunner) -> None:
    # 1. Network create
    net_post = respx.post(f"{BACKEND}/api/v1/network/networks").mock(
        return_value=httpx.Response(201, json={"id": "net-1", "name": "tenant-net"})
    )
    # 2. Subnet create
    sub_post = respx.post(f"{BACKEND}/api/v1/network/subnets").mock(
        return_value=httpx.Response(
            201,
            json={"id": "sub-1", "network_id": "net-1", "cidr": "10.0.0.0/24"},
        )
    )
    # 3. VM create
    vm_post = respx.post(f"{BACKEND}/api/v1/compute/servers").mock(
        return_value=httpx.Response(
            201,
            json={"id": "srv-1", "name": "web-01", "status": "BUILD"},
        )
    )
    # 4. Volume create
    vol_post = respx.post(f"{BACKEND}/api/v1/block-storage/volumes").mock(
        return_value=httpx.Response(201, json={"id": "vol-1", "size": 100})
    )
    # 5. Volume attach
    vol_attach = respx.post(f"{BACKEND}/api/v1/block-storage/volumes/vol-1/attach").mock(
        return_value=httpx.Response(200, json={"message": "attached"})
    )
    # 6. Floating IP allocate
    fip_post = respx.post(f"{BACKEND}/api/v1/network/floating-ips").mock(
        return_value=httpx.Response(
            201,
            json={"id": "fip-1", "floating_ip_address": "1.2.3.4"},
        )
    )
    # 7. Floating IP associate
    fip_assoc = respx.put(f"{BACKEND}/api/v1/network/floating-ips/fip-1/associate").mock(
        return_value=httpx.Response(
            200,
            json={"id": "fip-1", "port_id": "port-1"},
        )
    )

    # ---- 1. Create network
    r = runner.invoke(app, ["network", "create", "tenant-net"])
    assert r.exit_code == 0, r.stdout
    body = net_post.calls.last.request.read().decode()
    assert "tenant-net" in body

    # ---- 2. Create subnet on that network
    r = runner.invoke(
        app,
        ["subnet", "create", "tenant-sub", "--network", "net-1", "--cidr", "10.0.0.0/24"],
    )
    assert r.exit_code == 0, r.stdout
    body = sub_post.calls.last.request.read().decode()
    assert "net-1" in body
    assert "10.0.0.0/24" in body

    # ---- 3. Create VM on the network
    r = runner.invoke(
        app,
        [
            "vm",
            "create",
            "web-01",
            "--flavor",
            "m1.small",
            "--image",
            "ubuntu-22.04",
            "--network",
            "net-1",
        ],
    )
    assert r.exit_code == 0, r.stdout
    body = vm_post.calls.last.request.read().decode()
    assert "web-01" in body
    assert "net-1" in body

    # ---- 4. Create a volume
    r = runner.invoke(app, ["volume", "create", "data-01", "--size", "100"])
    assert r.exit_code == 0, r.stdout
    body = vol_post.calls.last.request.read().decode()
    assert "data-01" in body and "100" in body

    # ---- 5. Attach the volume to the VM
    r = runner.invoke(app, ["volume", "attach", "vol-1", "--server", "srv-1"])
    assert r.exit_code == 0, r.stdout
    body = vol_attach.calls.last.request.read().decode()
    assert "srv-1" in body

    # ---- 6. Allocate a floating IP
    r = runner.invoke(app, ["floating-ip", "allocate", "--floating-network", "ext-net"])
    assert r.exit_code == 0, r.stdout
    body = fip_post.calls.last.request.read().decode()
    assert "ext-net" in body

    # ---- 7. Associate the floating IP with the VM's port
    r = runner.invoke(app, ["floating-ip", "associate", "fip-1", "--port", "port-1"])
    assert r.exit_code == 0, r.stdout
    body = fip_assoc.calls.last.request.read().decode()
    assert "port-1" in body

    # All seven calls hit exactly once.
    assert net_post.call_count == 1
    assert sub_post.call_count == 1
    assert vm_post.call_count == 1
    assert vol_post.call_count == 1
    assert vol_attach.call_count == 1
    assert fip_post.call_count == 1
    assert fip_assoc.call_count == 1


@respx.mock
def test_cleanup_sequence(logged_in: None, runner: CliRunner) -> None:
    """The inverse: tear everything down."""
    fip_disassoc = respx.put(f"{BACKEND}/api/v1/network/floating-ips/fip-1/disassociate").mock(
        return_value=httpx.Response(200, json={"id": "fip-1", "port_id": None})
    )
    fip_release = respx.delete(f"{BACKEND}/api/v1/network/floating-ips/fip-1").mock(
        return_value=httpx.Response(200, json={"message": "released"})
    )
    vol_detach = respx.post(f"{BACKEND}/api/v1/block-storage/volumes/vol-1/detach").mock(
        return_value=httpx.Response(200, json={"message": "detached"})
    )
    vol_delete = respx.delete(f"{BACKEND}/api/v1/block-storage/volumes/vol-1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    vm_delete = respx.delete(f"{BACKEND}/api/v1/compute/servers/srv-1").mock(
        return_value=httpx.Response(200, json={"message": "deleting"})
    )
    sub_delete = respx.delete(f"{BACKEND}/api/v1/network/subnets/sub-1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )
    net_delete = respx.delete(f"{BACKEND}/api/v1/network/networks/net-1").mock(
        return_value=httpx.Response(200, json={"message": "deleted"})
    )

    for argv in [
        ["floating-ip", "disassociate", "fip-1"],
        ["floating-ip", "release", "fip-1", "--yes"],
        ["volume", "detach", "vol-1", "--server", "srv-1"],
        ["volume", "delete", "vol-1", "--yes"],
        ["vm", "delete", "srv-1", "--yes"],
        ["subnet", "delete", "sub-1", "--yes"],
        ["network", "delete", "net-1", "--yes"],
    ]:
        r = runner.invoke(app, argv)
        assert r.exit_code == 0, (argv, r.stdout, r.stderr)

    assert fip_disassoc.call_count == 1
    assert fip_release.call_count == 1
    assert vol_detach.call_count == 1
    assert vol_delete.call_count == 1
    assert vm_delete.call_count == 1
    assert sub_delete.call_count == 1
    assert net_delete.call_count == 1
