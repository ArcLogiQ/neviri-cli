"""Maps every backend route to its CLI command, or to an EXCLUDED reason.

The parity test (``test_parity.py``) asserts that the union of
``ROUTE_MAP`` and ``EXCLUDED`` equals the set of backend routes in
``backend_routes.json``. Anything else fails CI.

Conventions:

- ``ROUTE_MAP`` keys are ``(METHOD, PATH)`` tuples, exactly matching the
  snapshot. Values are the canonical ``neviri <subcommand>`` string.
- ``EXCLUDED`` keys are the same tuples, values are a short rationale.
- A given route is in exactly one of the two sets - never both.

When the backend adds a new route, this file fails parity until either:
  (a) a corresponding ``neviri`` command is added and mapped here, or
  (b) the route is intentionally added to ``EXCLUDED`` with rationale.
"""

from __future__ import annotations

# (method, path) -> short string describing the CLI surface that wraps it.
# Multiple routes can share the same CLI command (e.g. flavors GET).
ROUTE_MAP: dict[tuple[str, str], str] = {
    # ---------- compute (neviri vm) ----------
    ("GET", "/api/v1/compute/servers"): "vm list",
    ("POST", "/api/v1/compute/servers"): "vm create",
    ("GET", "/api/v1/compute/servers/{server_id}"): "vm get",
    (
        "PUT",
        "/api/v1/compute/servers/{server_id}",
    ): "vm update (not exposed; backend has it, CLI omits)",
    ("DELETE", "/api/v1/compute/servers/{server_id}"): "vm delete",
    ("POST", "/api/v1/compute/servers/{server_id}/action"): "vm start / stop / reboot",
    ("POST", "/api/v1/compute/servers/{server_id}/resize"): "vm resize",
    ("POST", "/api/v1/compute/servers/{server_id}/resize/confirm"): "vm resize-confirm",
    ("POST", "/api/v1/compute/servers/{server_id}/resize/revert"): "vm resize-revert",
    ("GET", "/api/v1/compute/servers/{server_id}/console"): "vm console",
    ("GET", "/api/v1/compute/flavors"): "vm flavors",
    ("GET", "/api/v1/compute/images"): "vm images",
    # ---------- block storage (neviri volume) ----------
    ("GET", "/api/v1/block-storage/volumes"): "volume list",
    ("POST", "/api/v1/block-storage/volumes"): "volume create",
    ("GET", "/api/v1/block-storage/volumes/{volume_id}"): "volume get",
    ("PUT", "/api/v1/block-storage/volumes/{volume_id}"): "volume update (not exposed; CLI omits)",
    ("DELETE", "/api/v1/block-storage/volumes/{volume_id}"): "volume delete",
    ("POST", "/api/v1/block-storage/volumes/{volume_id}/attach"): "volume attach",
    ("POST", "/api/v1/block-storage/volumes/{volume_id}/detach"): "volume detach",
    ("GET", "/api/v1/block-storage/snapshots"): "volume snapshots",
    ("POST", "/api/v1/block-storage/snapshots"): "volume snapshot",
    ("GET", "/api/v1/block-storage/snapshots/{snapshot_id}"): "volume snapshot-get",
    ("DELETE", "/api/v1/block-storage/snapshots/{snapshot_id}"): "volume snapshot-delete",
    # ---------- networking ----------
    ("GET", "/api/v1/network/networks"): "network list",
    ("POST", "/api/v1/network/networks"): "network create",
    ("GET", "/api/v1/network/networks/{network_id}"): "network get",
    ("PUT", "/api/v1/network/networks/{network_id}"): "network update (not exposed; CLI omits)",
    ("DELETE", "/api/v1/network/networks/{network_id}"): "network delete",
    ("GET", "/api/v1/network/subnets"): "subnet list",
    ("POST", "/api/v1/network/subnets"): "subnet create",
    ("GET", "/api/v1/network/subnets/{subnet_id}"): "subnet get",
    ("PUT", "/api/v1/network/subnets/{subnet_id}"): "subnet update (not exposed; CLI omits)",
    ("DELETE", "/api/v1/network/subnets/{subnet_id}"): "subnet delete",
    ("GET", "/api/v1/network/floating-ips"): "floating-ip list",
    ("POST", "/api/v1/network/floating-ips"): "floating-ip allocate",
    ("GET", "/api/v1/network/floating-ips/{floating_ip_id}"): "floating-ip get",
    ("DELETE", "/api/v1/network/floating-ips/{floating_ip_id}"): "floating-ip release",
    ("PUT", "/api/v1/network/floating-ips/{floating_ip_id}/associate"): "floating-ip associate",
    (
        "PUT",
        "/api/v1/network/floating-ips/{floating_ip_id}/disassociate",
    ): "floating-ip disassociate",
    # ---------- load balancers (neviri lb) ----------
    ("GET", "/api/v1/load-balancers"): "lb list",
    ("POST", "/api/v1/load-balancers"): "lb create",
    ("GET", "/api/v1/load-balancers/{lb_id}"): "lb get",
    ("PUT", "/api/v1/load-balancers/{lb_id}"): "lb update",
    ("DELETE", "/api/v1/load-balancers/{lb_id}"): "lb delete",
    ("GET", "/api/v1/load-balancers/{lb_id}/listeners"): "lb listener list",
    ("POST", "/api/v1/load-balancers/{lb_id}/listeners"): "lb listener create",
    ("GET", "/api/v1/load-balancers/{lb_id}/listeners/{listener_id}"): "lb listener get",
    (
        "PUT",
        "/api/v1/load-balancers/{lb_id}/listeners/{listener_id}",
    ): "lb listener update (not exposed)",
    ("DELETE", "/api/v1/load-balancers/{lb_id}/listeners/{listener_id}"): "lb listener delete",
    ("GET", "/api/v1/load-balancers/{lb_id}/pools"): "lb pool list",
    ("POST", "/api/v1/load-balancers/{lb_id}/pools"): "lb pool create",
    ("GET", "/api/v1/load-balancers/{lb_id}/pools/{pool_id}"): "lb pool get",
    ("PUT", "/api/v1/load-balancers/{lb_id}/pools/{pool_id}"): "lb pool update (not exposed)",
    ("DELETE", "/api/v1/load-balancers/{lb_id}/pools/{pool_id}"): "lb pool delete",
    ("GET", "/api/v1/load-balancers/{lb_id}/pools/{pool_id}/members"): "lb pool member-list",
    ("POST", "/api/v1/load-balancers/{lb_id}/pools/{pool_id}/members"): "lb pool member-add",
    (
        "GET",
        "/api/v1/load-balancers/{lb_id}/pools/{pool_id}/members/{member_id}",
    ): "lb pool member-get (not exposed)",
    (
        "PUT",
        "/api/v1/load-balancers/{lb_id}/pools/{pool_id}/members/{member_id}",
    ): "lb pool member-update (not exposed)",
    (
        "DELETE",
        "/api/v1/load-balancers/{lb_id}/pools/{pool_id}/members/{member_id}",
    ): "lb pool member-remove",
    (
        "POST",
        "/api/v1/load-balancers/{lb_id}/pools/{pool_id}/healthmonitor",
    ): "lb health-monitor create",
    (
        "GET",
        "/api/v1/load-balancers/{lb_id}/pools/{pool_id}/healthmonitor/{hm_id}",
    ): "lb health-monitor get",
    (
        "PUT",
        "/api/v1/load-balancers/{lb_id}/pools/{pool_id}/healthmonitor/{hm_id}",
    ): "lb health-monitor update (not exposed)",
    (
        "DELETE",
        "/api/v1/load-balancers/{lb_id}/pools/{pool_id}/healthmonitor/{hm_id}",
    ): "lb health-monitor delete",
    # ---------- object storage ----------
    ("GET", "/api/v1/object-storage/containers"): "object bucket list",
    ("POST", "/api/v1/object-storage/containers"): "object bucket create",
    ("GET", "/api/v1/object-storage/containers/{container_name}"): "object bucket get",
    ("DELETE", "/api/v1/object-storage/containers/{container_name}"): "object bucket delete",
    ("GET", "/api/v1/object-storage/containers/{container_name}/objects"): "object list",
    (
        "PUT",
        "/api/v1/object-storage/containers/{container_name}/objects/{object_name:path}",
    ): "object put",
    (
        "GET",
        "/api/v1/object-storage/containers/{container_name}/objects/{object_name:path}",
    ): "object get",
    (
        "DELETE",
        "/api/v1/object-storage/containers/{container_name}/objects/{object_name:path}",
    ): "object delete",
    # ---------- databases ----------
    # MongoDB
    ("GET", "/api/v1/database/all-databases"): "db mongo list",
    ("POST", "/api/v1/database/create-deployment"): "db mongo create",
    ("DELETE", "/api/v1/database/delete-database/{database_id}"): "db mongo delete",
    ("GET", "/api/v1/database/status/{database_id}"): "db mongo status",
    ("PUT", "/api/v1/database/scale-database/{database_id}"): "db mongo scale",
    # MySQL
    ("GET", "/api/v1/mysql/all-mysql"): "db mysql list",
    ("POST", "/api/v1/mysql/create-mysql"): "db mysql create",
    ("DELETE", "/api/v1/mysql/delete-mysql/{database_id}"): "db mysql delete",
    ("GET", "/api/v1/mysql/status-mysql/{database_id}"): "db mysql status",
    ("PUT", "/api/v1/mysql/scale-mysql/{database_id}"): "db mysql scale",
    ("GET", "/api/v1/mysql/flavors"): "db mysql flavors",
    # PostgreSQL
    ("GET", "/api/v1/postgres/all-postgres"): "db pg list",
    ("POST", "/api/v1/postgres/create-postgres"): "db pg create",
    ("DELETE", "/api/v1/postgres/delete-postgres/{database_id}"): "db pg delete",
    ("GET", "/api/v1/postgres/status-postgres/{database_id}"): "db pg status",
    ("PUT", "/api/v1/postgres/scale-postgres/{database_id}"): "db pg scale",
    ("GET", "/api/v1/postgres/flavors"): "db pg flavors",
    # ---------- backups / restore (universal endpoint) ----------
    ("POST", "/api/v1/backup/create"): "db <engine> backup",
    ("GET", "/api/v1/backup/list"): "db <engine> backups",
    ("DELETE", "/api/v1/backup/delete/{backup_id}"): "db <engine> backup-delete",
    ("POST", "/api/v1/restore/initiate"): "db <engine> restore",
    ("GET", "/api/v1/restore/status/{backup_id}"): "db <engine> restore-status",
    # ---------- apps & deployments ----------
    ("GET", "/api/v1/apps"): "app list",
    ("POST", "/api/v1/apps"): "app create",
    ("GET", "/api/v1/apps/{app_id}"): "app get",
    ("DELETE", "/api/v1/apps/{app_id}"): "app delete",
    ("POST", "/api/v1/apps/{app_id}/upload"): "app upload",
    ("GET", "/api/v1/apps/{app_id}/deployments"): "app deployments",
    ("GET", "/api/v1/apps/{app_id}/env"): "app env-list",
    ("POST", "/api/v1/apps/{app_id}/env"): "app env-set",
    ("DELETE", "/api/v1/apps/{app_id}/env/{env_id}"): "app env-unset",
    ("GET", "/api/v1/deployments/{deployment_id}"): "deploy get",
    ("GET", "/api/v1/deployments/{deployment_id}/manifests"): "deploy manifests",
    ("POST", "/api/v1/deployments/{deployment_id}/build"): "deploy build",
    ("POST", "/api/v1/deployments/{deployment_id}/deploy"): "deploy deploy",
    ("POST", "/api/v1/deployments/{deployment_id}/service"): "deploy service",
    ("POST", "/api/v1/deployments/{deployment_id}/ingress"): "deploy ingress",
    # ---------- credits ----------
    ("GET", "/api/v1/credits/balance"): "credit balance",
    ("GET", "/api/v1/credits/status"): "credit status",
    ("GET", "/api/v1/credits/transactions"): "credit history",
    # ---------- payment ----------
    ("GET", "/api/v1/payment/history"): "payment list",
    ("GET", "/api/v1/payment/summary"): "payment summary",
    ("GET", "/api/v1/payment/monthly-summary"): "payment monthly-summary",
    ("GET", "/api/v1/payment/cluster-paid-total/{cluster_name}"): "payment cluster-total",
    ("GET", "/api/v1/payment/receipt/{payment_id}"): "payment receipt",
    ("GET", "/api/v1/payment/invoice/{payment_id}"): "payment invoice",
    ("GET", "/api/v1/payment/monthly-invoice"): "payment monthly-invoice",
    ("POST", "/api/v1/payment/razorpay/create-order"): "credit top-up",
    # ---------- payment method ----------
    ("GET", "/api/v1/payment-method/payment-method-status"): "payment method status / list",
    ("DELETE", "/api/v1/payment-method/remove-payment-method"): "payment method delete",
}


# Routes the CLI intentionally does NOT wrap. Each entry must have a rationale
# so future readers know whether the omission is on purpose or an oversight.
EXCLUDED: dict[tuple[str, str], str] = {
    # ---------- deprecated VM router (superseded by compute/servers per ADR 0001) ----------
    ("GET", "/api/v1/vm/all"): "deprecated; CLI uses /compute/servers/* per ADR 0001",
    ("POST", "/api/v1/vm/create"): "deprecated; CLI uses /compute/servers/* per ADR 0001",
    ("GET", "/api/v1/vm/{vm_id}"): "deprecated; CLI uses /compute/servers/* per ADR 0001",
    ("DELETE", "/api/v1/vm/{vm_id}"): "deprecated; CLI uses /compute/servers/* per ADR 0001",
    ("POST", "/api/v1/vm/{vm_id}/start"): "deprecated; CLI uses /compute/servers/*",
    ("POST", "/api/v1/vm/{vm_id}/stop"): "deprecated; CLI uses /compute/servers/*",
    ("GET", "/api/v1/vm/{vm_id}/status"): "deprecated; CLI uses /compute/servers/*",
    # ---------- content / support surfaces (not on the CLI roadmap) ----------
    ("GET", "/api/v1/blog/all"): "content surface; not on CLI roadmap",
    ("GET", "/api/v1/blog/public"): "content surface; not on CLI roadmap",
    ("GET", "/api/v1/blog/admin/{blog_id}"): "content surface; not on CLI roadmap",
    ("GET", "/api/v1/blog/slug/{slug}"): "content surface; not on CLI roadmap",
    ("POST", "/api/v1/blog/create"): "content surface; not on CLI roadmap",
    ("PUT", "/api/v1/blog/update/{blog_id}"): "content surface; not on CLI roadmap",
    ("DELETE", "/api/v1/blog/{blog_id}"): "content surface; not on CLI roadmap",
    ("POST", "/api/v1/blog/{blog_id}/interaction"): "content surface; not on CLI roadmap",
    ("PATCH", "/api/v1/blog/{blog_id}/publish"): "content surface; not on CLI roadmap",
    ("POST", "/api/v1/support/send-email"): "support ticket flow; not on CLI roadmap",
    # ---------- health probes (implicit version-compat check; not a user command) ----------
    ("GET", "/api/v1/health"): "implicit in version compat check (proposal 4.8)",
    ("GET", "/api/v1/health/ready"): "implicit in version compat check (proposal 4.8)",
    # ---------- internal routers (admin-only; not for end users) ----------
    ("POST", "/api/v1/internal/credits/grant"): "internal X-Internal-API-Key route; admin Postman",
    # ---------- image upload (deferred - on the original proposal but not Phase 2) ----------
    ("POST", "/api/v1/image/upload-azure"): "deferred (proposal had neviri image; Phase 3 work)",
    ("POST", "/api/v1/image/upload-azure-base64"): "deferred (Phase 3 work)",
    # ---------- backup: dashboard-only UX surfaces ----------
    ("POST", "/api/v1/backup/register"): "internal callback from backup scripts; not user-facing",
    ("GET", "/api/v1/backup/details/{backup_id}"): "dashboard UX; CLI users get list output",
    ("GET", "/api/v1/backup/download/{backup_id}"): "dashboard UX; not on CLI roadmap",
    ("GET", "/api/v1/backup/download-data/{backup_id}"): "dashboard UX; not on CLI roadmap",
    ("GET", "/api/v1/backup/preview/{backup_id}"): "dashboard UX; not on CLI roadmap",
    ("GET", "/api/v1/backup/browse/{backup_id}"): "dashboard UX; not on CLI roadmap",
    # backup scheduling (no CLI surface for it in Phase 2)
    ("POST", "/api/v1/backup/automatic/schedule"): "scheduling not in Phase 2 CLI scope",
    ("POST", "/api/v1/backup/automatic/unschedule"): "scheduling not in Phase 2 CLI scope",
    ("GET", "/api/v1/backup/automatic/cost"): "cost estimator; niche; not on CLI roadmap",
    ("GET", "/api/v1/backup/automatic/list"): "scheduling not in Phase 2 CLI scope",
    # ---------- per-engine backup routers (duplicates of the universal /backup/*) ----------
    ("POST", "/api/v1/mysql-backup/create"): "CLI uses unified /backup/create with database_type",
    ("GET", "/api/v1/mysql-backup/list"): "CLI uses unified /backup/list",
    (
        "GET",
        "/api/v1/mysql-backup/details/{backup_id}",
    ): "duplicate of /backup/details (dashboard UX)",
    ("DELETE", "/api/v1/mysql-backup/delete/{backup_id}"): "CLI uses unified /backup/delete",
    ("GET", "/api/v1/mysql-backup/download/{backup_id}"): "duplicate of /backup/download",
    ("GET", "/api/v1/mysql-backup/download-data/{backup_id}"): "duplicate of /backup/download-data",
    ("GET", "/api/v1/mysql-backup/preview/{backup_id}"): "duplicate of /backup/preview",
    ("GET", "/api/v1/mysql-backup/browse/{backup_id}"): "duplicate of /backup/browse",
    ("POST", "/api/v1/mysql-backup/automatic/schedule"): "scheduling not in CLI scope",
    ("POST", "/api/v1/mysql-backup/automatic/unschedule"): "scheduling not in CLI scope",
    ("GET", "/api/v1/mysql-backup/automatic/list"): "scheduling not in CLI scope",
    ("POST", "/api/v1/postgres-backup/create"): "CLI uses unified /backup/create",
    ("GET", "/api/v1/postgres-backup/list"): "CLI uses unified /backup/list",
    ("GET", "/api/v1/postgres-backup/details/{backup_id}"): "duplicate of /backup/details",
    ("DELETE", "/api/v1/postgres-backup/delete/{backup_id}"): "CLI uses unified /backup/delete",
    ("GET", "/api/v1/postgres-backup/download/{backup_id}"): "duplicate of /backup/download",
    ("POST", "/api/v1/postgres-backup/automatic/schedule"): "scheduling not in CLI scope",
    ("POST", "/api/v1/postgres-backup/automatic/unschedule"): "scheduling not in CLI scope",
    ("GET", "/api/v1/postgres-backup/automatic/list"): "scheduling not in CLI scope",
    # ---------- restore extras ----------
    (
        "GET",
        "/api/v1/restore/history",
    ): "not yet on CLI roadmap; can add to db <engine> restore-history",
    ("POST", "/api/v1/restore/cancel/{backup_id}"): "not yet on CLI roadmap",
    # ---------- database observability (deferred to neviri monitor in a later story) ----------
    ("GET", "/api/v1/database/iops/{cluster_name}"): "observability surface; future neviri monitor",
    ("GET", "/api/v1/database/usage-report"): "observability surface; future neviri monitor",
    (
        "GET",
        "/api/v1/database/usage/{cluster_name}",
    ): "observability surface; future neviri monitor",
    # ---------- networking routers (deferred to a later story) ----------
    ("GET", "/api/v1/network/routers"): "neviri router not on Phase 2 roadmap",
    ("POST", "/api/v1/network/routers"): "neviri router not on Phase 2 roadmap",
    ("GET", "/api/v1/network/routers/{router_id}"): "neviri router not on Phase 2 roadmap",
    ("PUT", "/api/v1/network/routers/{router_id}"): "neviri router not on Phase 2 roadmap",
    ("DELETE", "/api/v1/network/routers/{router_id}"): "neviri router not on Phase 2 roadmap",
    ("PUT", "/api/v1/network/routers/{router_id}/add-interface"): "neviri router not on roadmap",
    ("PUT", "/api/v1/network/routers/{router_id}/remove-interface"): "neviri router not on roadmap",
    # ---------- Razorpay verification / bulk order (browser-only flow, not CLI) ----------
    (
        "POST",
        "/api/v1/payment/razorpay/verify-payment",
    ): "browser-only Razorpay flow; CLI can't complete",
    ("POST", "/api/v1/payment/razorpay/create-bulk-order"): "bulk top-up not in Phase 2 CLI scope",
    # ---------- payment-method endpoints that require Razorpay JS SDK (browser-only) ----------
    ("POST", "/api/v1/payment-method/setup-customer"): "Razorpay JS flow; browser-only",
    ("POST", "/api/v1/payment-method/create-setup-intent"): "Razorpay JS flow; browser-only",
    ("POST", "/api/v1/payment-method/save-payment-method"): "Razorpay JS flow; browser-only",
    ("PUT", "/api/v1/payment-method/update-payment-method"): "Razorpay JS flow; browser-only",
}
