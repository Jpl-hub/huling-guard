from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RuntimeReleaseBundle:
    release_dir: Path
    manifest_path: Path
    checkpoint_path: Path
    train_config_path: Path
    runtime_config_path: Path
    summary_json_path: Path | None = None
    summary_md_path: Path | None = None
    metadata: dict[str, Any] | None = None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_runtime_release_bundle(release_dir: str | Path) -> RuntimeReleaseBundle:
    base = Path(release_dir).resolve()
    manifest_path = base / "release_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    def _resolve(relative_path: str | None) -> Path | None:
        if relative_path is None:
            return None
        path = Path(relative_path)
        if path.is_absolute():
            return path
        return (base / path).resolve()

    checkpoint_path = _resolve(payload.get("checkpoint"))
    train_config_path = _resolve(payload.get("train_config"))
    runtime_config_path = _resolve(payload.get("runtime_config"))
    if checkpoint_path is None or not checkpoint_path.is_file():
        raise FileNotFoundError(checkpoint_path or "<checkpoint>")
    if train_config_path is None or not train_config_path.is_file():
        raise FileNotFoundError(train_config_path or "<train_config>")
    if runtime_config_path is None or not runtime_config_path.is_file():
        raise FileNotFoundError(runtime_config_path or "<runtime_config>")

    reports = payload.get("reports", {})
    return RuntimeReleaseBundle(
        release_dir=base,
        manifest_path=manifest_path,
        checkpoint_path=checkpoint_path,
        train_config_path=train_config_path,
        runtime_config_path=runtime_config_path,
        summary_json_path=_resolve(reports.get("summary_json")),
        summary_md_path=_resolve(reports.get("summary_md")),
        metadata=payload,
    )


def verify_runtime_release_bundle(release_dir: str | Path) -> dict[str, Any]:
    bundle = load_runtime_release_bundle(release_dir)
    metadata = bundle.metadata or {}
    artifacts = metadata.get("artifacts", {})
    checks: list[dict[str, Any]] = []

    for name, artifact in artifacts.items():
        if artifact is None:
            continue
        relative_path = artifact.get("path")
        if relative_path is None:
            checks.append({"name": name, "status": "missing_metadata"})
            continue
        path = (bundle.release_dir / relative_path).resolve()
        if not path.is_file():
            checks.append(
                {
                    "name": name,
                    "status": "missing_file",
                    "path": str(path),
                }
            )
            continue
        size_bytes = path.stat().st_size
        sha256 = _sha256(path)
        expected_size = artifact.get("size_bytes")
        expected_sha = artifact.get("sha256")
        checks.append(
            {
                "name": name,
                "status": "ok" if size_bytes == expected_size and sha256 == expected_sha else "mismatch",
                "path": str(path),
                "size_bytes": size_bytes,
                "expected_size_bytes": expected_size,
                "sha256": sha256,
                "expected_sha256": expected_sha,
            }
        )

    missing_or_bad = [check for check in checks if check["status"] != "ok"]
    return {
        "release_dir": str(bundle.release_dir),
        "manifest_path": str(bundle.manifest_path),
        "layout_version": metadata.get("layout_version"),
        "generated_at_utc": metadata.get("generated_at_utc"),
        "ok": not missing_or_bad,
        "checked_artifacts": len(checks),
        "checks": checks,
    }


def format_runtime_release_verification(summary: dict[str, Any]) -> str:
    lines = [
        "# 运行时发布包校验",
        "",
        f"- release_dir: {summary['release_dir']}",
        f"- layout_version: {summary.get('layout_version')}",
        f"- generated_at_utc: {summary.get('generated_at_utc') or 'n/a'}",
        f"- checked_artifacts: {summary['checked_artifacts']}",
        f"- ok: {'yes' if summary['ok'] else 'no'}",
        "",
        "## 文件检查",
    ]
    for check in summary["checks"]:
        lines.append(
            f"- {check['name']}: {check['status']}"
            + (f", path={check.get('path')}" if check.get("path") else "")
        )
    return "\n".join(lines) + "\n"
