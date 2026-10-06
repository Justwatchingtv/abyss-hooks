#!/usr/bin/env python3
"""Qualify community source artifacts against the pinned Black Market fixture graph."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {"schemaVersion", "name", "topology", "source", "contract", "license"}
SLUG = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
INTEGRATION_FIELDS = {"schemaVersion", "kind", "authorId", "maximumDeveloperFeeBps", "terms", "bounds"}
BOUND_LIMITS = {
    "minimumTickSpacing": (1, 32767),
    "maximumTickSpacing": (1, 32767),
    "maximumPositions": (1, 32),
    "maximumOracleCardinality": (2, 4096),
    "feeModeFlags": (1, 3),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def integration_inputs(folder):
    path = folder / "integration.json"
    require(path.is_file(), f"Missing integration.json: {folder}")
    data = json.loads(path.read_text(), object_pairs_hook=unique_object)
    require(isinstance(data, dict) and set(data) == INTEGRATION_FIELDS, "Exact integration fields required")
    require(type(data["schemaVersion"]) is int and data["schemaVersion"] == 1, "Unsupported integration schemaVersion")
    require(data["kind"] in ("reference", "submission"), "Unsupported integration kind")
    author = data["authorId"]
    if data["kind"] == "reference":
        require(folder.name in ("reference-shared", "reference-bound"), "Only canonical example folders may declare reference kind")
        require(author is None and data["maximumDeveloperFeeBps"] == 0, "Reference examples cannot propose author economics")
    else:
        require(isinstance(author, str) and re.fullmatch(r"0x[0-9a-fA-F]{40}", author) and int(author, 16) != 0, "authorId must be a nonzero 20-byte address")
    ceiling = data["maximumDeveloperFeeBps"]
    require(type(ceiling) is int and 0 <= ceiling < 10000, "maximumDeveloperFeeBps must be an integer in 0..9999")
    require(isinstance(data["terms"], str) and data["terms"].strip(), "Nonempty author terms are required")
    bounds = data["bounds"]
    require(isinstance(bounds, dict) and set(bounds) == set(BOUND_LIMITS), "Exact five-member registry bounds required")
    for name, (minimum, maximum) in BOUND_LIMITS.items():
        require(type(bounds[name]) is int and minimum <= bounds[name] <= maximum, f"bounds.{name} must be an integer in {minimum}..{maximum}")
    require(bounds["minimumTickSpacing"] <= bounds["maximumTickSpacing"], "Reversed tick-spacing bounds")
    return data


def write_review_reports(rows, output):
    reports = []
    for folder, row in rows:
        declared = integration_inputs(folder)
        pins = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(folder.iterdir())}
        report = {
            "schemaVersion": 1, "name": row["name"], "upstream": json.loads((ROOT / "scripts/upstream.json").read_text()),
            "declared": declared,
            "sourceIdentity": row,
            "sourceFileSha256": pins,
            "inputValidation": {"passed": True, "scope": "Syntax and canonical registry ranges only; not author-control proof, economic approval, or execution under declared bounds"},
            "admissionReady": False,
            "pendingAdmission": [
                "Complete source/runtime/dependency review and approved artifactDigest/reviewManifestDigest/termsDigest",
                "Approve declared bounds and ceiling against the target registry's immutable protocol maximum",
                "Target chain, registry and core; registered adapterId and dependencyDigest",
                "Fixed protocol treasury and denominator (zero or 4..10)",
                "Deployed graph addresses/runtime hashes, immutable typed deployer/chunks and shared root or bound constructor provenance",
                "Exact approved envelope, configBoundsDigest, profileId and ProfileRegistrationV1",
                "Current author controller, stable-ID nonce, deadline and chain/registry-bound EOA/ERC-1271 authorization",
                "Registry administrator registration; PR merge does not submit a transaction",
            ],
        }
        (output / f"{row['name']}.registration-inputs.json").write_text(json.dumps(report, indent=2) + "\n")
        reports.append(report)
    lines = ["# Hook PR input review", "", "Declarations below are range-validated, not admitted. Author control, proposed bounds execution and production economics are unproven.", ""]
    for report in reports:
        data = report["declared"]
        lines.extend([f"## {report['name']}", "", f"- Kind: `{data['kind']}`; topology: `{report['sourceIdentity']['topology']}`",
                      f"- Stable authorId: `{data['authorId']}`; proposed ceiling: `{data['maximumDeveloperFeeBps']}` bps",
                      f"- Bounds: `{json.dumps(data['bounds'], sort_keys=True)}`",
                      f"- Exact terms, file pins and pending inputs: `{report['name']}.registration-inputs.json`", ""])
    (output / "PR-REVIEW.md").write_text("\n".join(lines) + "\n")


def submissions(root):
    require(root.is_dir() and not root.is_symlink(), "Missing plain hooks directory")
    rows = []
    for folder in sorted(root.iterdir()):
        require(folder.is_dir() and not folder.is_symlink() and SLUG.fullmatch(folder.name), f"Invalid hook directory: {folder}")
        files = list(folder.iterdir())
        require(all(p.is_file() and not p.is_symlink() for p in files), f"Only regular files allowed: {folder}")
        require(all(p.name in {"hook.json", "integration.json", "review.md"} or (p.suffix == ".sol" and IDENTIFIER.fullmatch(p.stem)) for p in files), f"Unexpected submission file: {folder}")
        manifest = folder / "hook.json"
        require(manifest.is_file(), f"Missing hook.json: {folder}")
        row = json.loads(manifest.read_text(), object_pairs_hook=unique_object)
        require(isinstance(row, dict) and set(row) == FIELDS, f"Exact manifest fields required: {folder}")
        require(type(row["schemaVersion"]) is int and row["schemaVersion"] == 1, "Unsupported schemaVersion")
        require(row["name"] == folder.name, "Manifest name must equal directory slug")
        require(row["topology"] in {"SharedV4", "PoolBoundV4"}, "Unsupported topology")
        require(isinstance(row["contract"], str) and IDENTIFIER.fullmatch(row["contract"]), "Invalid concrete contract name")
        source = row["source"]
        require(isinstance(source, str) and source.endswith(".sol") and IDENTIFIER.fullmatch(source[:-4]), "Source must be a local Solidity filename")
        require((folder / source).is_file(), "Missing selected source")
        require(isinstance(row["license"], str) and re.fullmatch(r"[A-Za-z0-9.+-]+", row["license"]), "Declare a single SPDX license identifier")
        review = folder / "review.md"
        require(review.is_file() and review.read_text().strip(), "Missing author review.md")
        for path in files:
            if path.suffix == ".sol":
                require(f"// SPDX-License-Identifier: {row['license']}" in path.read_text().splitlines(), f"SPDX declaration mismatch: {path}")
        integration_inputs(folder)
        rows.append((folder, row))
    require(rows, "Empty hook catalogue cannot pass qualification")
    return rows


def run(argv, cwd, output, label, env=None):
    result = subprocess.run(argv, cwd=cwd, env=env, text=True, capture_output=True)
    (output / f"{label}.stdout.log").write_text(result.stdout)
    (output / f"{label}.stderr.log").write_text(result.stderr)
    require(result.returncode == 0, f"{label} failed; inspect {output}")
    return result.stdout


def collect_evidence(export, workflow, contracts):
    codec_rows = []
    choices = []
    for path in sorted(export.glob("*.json")):
        row = workflow.load_json(path)
        if row["schema"] == "black-market.launch-codec-evidence.v1":
            codec_rows.append(workflow.codec_evidence(path, contracts=contracts))
        elif row["schema"] == "black-market.creator-choices-evidence.v1":
            peer = row["codecEvidence"]
            require(isinstance(peer, str) and Path(peer).name == peer, "Invalid creator-choice evidence reference")
            paired = workflow.load_json(export / peer)
            require(paired["schema"] == "black-market.launch-codec-evidence.v1", "Creator choice must reference codec evidence")
            for field in ("chainId", "core", "registry", "adapter", "token", "hook", "profileId"):
                require(row[field] == paired[field], f"Creator-choice identity mismatch: {field}")
            require(row["cardinality"] == 4096 and row["maxAbsTickMove"] in (1, 6, 17), "Unexpected canonical oracle menu")
            require(row["oracleConfigId"] == paired["config"]["oracleConfigId"], "Creator-choice oracle mismatch")
            disabled = row["externalLiquidityDisabled"]
            require(type(disabled) is bool and disabled == paired["config"]["externalLiquidityDisabled"], "Creator-choice LP policy mismatch")
            require(row["preOpeningAddRejected"] is True and row["preOpeningRemoveRejected"] is True and row["launchCustodySealed"] is True, "Creator-choice custody invariant failed")
            require(row["externalAddSucceeded"] is (not disabled) and row["externalRemoveSucceeded"] is (not disabled), "Creator-choice external LP behavior failed")
            require(row["authorPaid"] > 0 and row["ownerPaid"] > 0, "Creator-choice payout failed")
            choices.append(row)
        else:
            raise ValueError(f"Unknown exported evidence schema: {path}")
    require({row["version"] for row in codec_rows} == {4, 5}, "Missing topology codec execution evidence")
    require({(row["maxAbsTickMove"], row["externalLiquidityDisabled"]) for row in choices} == {(move, disabled) for move in (1, 6, 17) for disabled in (False, True)}, "Incomplete creator-choice execution matrix")
    return codec_rows, choices


def execute_fixture(workflow, manifest, contracts, upstream, output, environment):
    fixture = workflow.validate_manifest(manifest, source_root=upstream)
    output.mkdir()
    shutil.copyfile(manifest, output / "submitted-manifest.json")
    artifacts = workflow.check_artifact_pins(fixture, contracts=contracts, source_root=upstream, solc=workflow.compiler_executable(None), output=output)
    selected = output / "qualified-hook-artifact.json"
    shutil.copyfile(artifacts[0]["file"], selected)
    env = dict(environment)
    bound = fixture["template"]["topology"] == "PoolBoundV4"
    env["HOOK_QUALIFICATION_BOUND_ARTIFACT" if bound else "HOOK_QUALIFICATION_SHARED_ARTIFACT"] = str(selected)
    (contracts / "deployments").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="community-qualification-", dir=contracts / "deployments") as temporary:
        export = Path(temporary)
        env["HOOK_QUALIFICATION_EXPORT"] = str(export.relative_to(contracts))
        resolved = run(["forge", "config"], contracts, output, "foundry-profile-config", env)
        config = export / "external-artifact.foundry.toml"
        config.write_text(resolved + '\n[[profile.launch_lifecycle_v1.fs_permissions]]\naccess = "read"\npath = ' + json.dumps(str(selected)) + "\n")
        env["FOUNDRY_CONFIG"] = str(config)
        run(["forge", "test", "--match-path", workflow.TEST, "-vvv", "--root", str(contracts)], contracts, output, "foundry-qualification", env)
        run(["forge", "script", workflow.SMOKE, "--sig", "run()", "-vvvv", "--root", str(contracts)], contracts, output, "headless-runtime-smoke", env)
        parity, choices = collect_evidence(export, workflow, contracts)
        executions = [row for row in parity if row["version"] == fixture["template"]["configVersion"]]
        require(executions and all(row["hookArtifact"] == str(selected) and row["hookArtifactFileSha256"] == artifacts[0]["fileSha256"] and row["hookCreationCodeHash"] == artifacts[0]["creationCodeHash"] for row in executions), "Executed selected artifact identity mismatch")
        archive = output / "solidity-evidence"
        archive.mkdir()
        for path in export.glob("*.json"):
            shutil.copyfile(path, archive / path.name)
    result = {"locallyQualified": True, "fixtureOnly": True, "productionAdmission": False, "artifactEvidence": artifacts, "fixtureExecutionEvidence": parity, "creatorChoiceEvidence": choices}
    (output / "qualification-result.json").write_text(json.dumps(workflow.json_safe(result), indent=2) + "\n")
    return result


def qualify(upstream, output, rows):
    pin = json.loads((ROOT / "scripts/upstream.json").read_text())
    require(upstream != ROOT and (upstream / "contracts").is_dir(), "Use a separate integration checkout")
    require(subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=upstream, text=True).strip() == pin["revision"], "Integration checkout differs from pinned revision")
    require(subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "contracts", "scripts"], cwd=upstream).returncode == 0, "Integration sources must be unmodified")
    require(not output.exists(), "Use a new evidence output directory")
    output.mkdir(parents=True)
    write_review_reports(rows, output)
    contracts = upstream / "contracts"
    stage = contracts / "src/community"
    require(not stage.exists(), "Refusing to replace existing community directory")
    remappings = contracts / "remappings.txt"
    original = remappings.read_bytes()
    environment = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "USER", "LANG", "LC_ALL", "TMPDIR", "SSL_CERT_FILE", "SSL_CERT_DIR"}}
    environment["FOUNDRY_PROFILE"] = "launch_lifecycle_v1"
    # Load only the integration checkout's pinned qualification code.
    sys.path.insert(0, str(upstream / "scripts"))
    spec = importlib.util.spec_from_file_location("qualification", upstream / "scripts/qualify_launch_hook_v1.py")
    workflow = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(workflow)
    try:
        stage.mkdir()
        remappings.write_bytes(original + b"\n@black-market/=src/\n")
        for folder, row in rows:
            target = stage / folder.name
            target.mkdir()
            for source in folder.glob("*.sol"):
                shutil.copyfile(source, target / source.name)
        manager_environment = dict(environment)
        manager_environment.pop("FOUNDRY_PROFILE")
        run(["forge", "build", "src/PoolManager.sol"], contracts / "lib/v4-core", output, "pool-manager-build", manager_environment)
        run(["forge", "build"], contracts, output, "build", environment)
        for folder, row in rows:
            label = row["name"]
            print(f"Qualifying {label} ({row['topology']})", flush=True)
            artifact = contracts / "out" / row["source"] / f"{row['contract']}.json"
            require(artifact.is_file(), f"No concrete artifact produced: {label}")
            # Pin bytes before any EVM execution; independently reconstruct from compiler sources.
            measured = workflow.artifact_evidence(str(artifact), contracts)
            metadata = workflow.artifact_metadata(json.loads(artifact.read_text()), artifact)
            require(metadata["settings"]["compilationTarget"] == {f"src/community/{label}/{row['source']}": row["contract"]}, f"Artifact target collision or mismatch: {label}")
            require(0 < measured["templateRuntimeBytes"] <= 24576, f"Runtime portability limit: {label}")
            require(0 < measured["creationBytes"] <= 49152, f"Creation portability limit: {label}")
            fixture = json.loads((contracts / "config/launch-hook-submission-v1.fixture.example.json").read_text())
            fixture["label"] = f"Community CI fixture: {label}; not an admission application"
            bound = row["topology"] == "PoolBoundV4"
            fixture["template"].update(topology=row["topology"], configVersion=5 if bound else 4, hookArtifact=str(artifact), deployerArtifact="PoolHookDeployerV1.sol:PoolHookDeployerV1" if bound else "SharedHookDeployerV1.sol:SharedHookDeployerV1")
            fixture["provenance"]["artifacts"] = [{"identifier": str(artifact), **{key: measured[key] for key in ("creationCodeHash", "deployedBytecodeHash", "immutableReferencesDigest")}}]
            manifest = output / f"{label}.fixture.json"
            manifest.write_text(json.dumps(fixture, indent=2) + "\n")
            qualification = execute_fixture(workflow, manifest, contracts, upstream, output / label, environment)
            report_path = output / f"{label}.registration-inputs.json"
            report = json.loads(report_path.read_text())
            inputs = report["declared"]
            report["derivedRegistryFields"] = {
                "topology": 2 if bound else 1, "configVersion": 5 if bound else 4,
                "economicVersion": 3, "capabilities": 123, "flags": 0,
                "callbackFlags": 0x1afc, "callbackMask": 0x3fff,
                "configSchema": "0x" + workflow.codec.config_schema(5 if bound else 4).hex(),
                "configBoundsDigest": "0x" + workflow.codec.config_bounds_digest(inputs["bounds"]).hex(),
            }
            report["measuredArtifact"] = qualification["artifactEvidence"][0]
            report["runtimeQualification"] = {"passed": True, "fixtureOnly": True, "declaredBoundsAndEconomicsExecuted": False, "evidence": f"{label}/qualification-result.json"}
            report_path.write_text(json.dumps(report, indent=2) + "\n")
        (output / "catalogue-result.json").write_text(json.dumps({"upstream": pin, "hooks": [row for _, row in rows], "locallyQualified": True, "productionAdmission": False}, indent=2) + "\n")
    finally:
        remappings.write_bytes(original)
        shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, default=ROOT / ".integration/black-market")
    parser.add_argument("--output", type=Path, default=ROOT / "evidence")
    parser.add_argument("--structure-only", action="store_true")
    args = parser.parse_args()
    try:
        rows = submissions(ROOT / "hooks")
        print(f"Validated {len(rows)} source submissions", flush=True)
        if args.structure_only:
            output = args.output.resolve()
            require(not output.exists(), "Use a new evidence output directory")
            output.mkdir(parents=True)
            write_review_reports(rows, output)
        else:
            qualify(args.upstream.resolve(), args.output.resolve(), rows)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"Hook checks refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
