# Contributing

## Submission

Copy `hooks/reference-shared` or `hooks/reference-bound` to `hooks/<slug>`. Use a lowercase kebab-case slug, rename the source and contract, and update the declarations.

Each folder must contain:

| File | Contents |
| --- | --- |
| `hook.json` | `schemaVersion: 1`, matching `name`, `topology`, `source`, `contract`, SPDX `license` |
| `integration.json` | Proposed registry inputs listed below |
| `review.md` | Formula and rounding; boundary inputs/outputs; changes, dependencies, authority and risks; input rationale and verification evidence |
| `*.sol` | Complete sources with matching SPDX headers |

Additional local Solidity files are allowed. No nested directories, symlinks, scripts, generated artifacts or other file types. `source` must be a local filename. Imports use `@black-market/` for upstream `contracts/src/`; upstream Uniswap and Solady remappings remain available.

### Integration inputs

`integration.json` requires exactly these fields:

| Field | Accepted values |
| --- | --- |
| `schemaVersion` | Integer `1` |
| `kind` | `submission`; `reference` is reserved for the two examples |
| `authorId` | Nonzero `0x`-prefixed 20-byte address, identifying the stable author—not the live payout wallet |
| `maximumDeveloperFeeBps` | Integer `0..9999`; zero requests no developer allocation |
| `terms` | Nonempty string with the proposed author/economic terms |
| `bounds.minimumTickSpacing` | Integer `1..32767` |
| `bounds.maximumTickSpacing` | Integer `1..32767`, at least the minimum |
| `bounds.maximumPositions` | Integer `1..32` |
| `bounds.maximumOracleCardinality` | Integer `2..4096` |
| `bounds.feeModeFlags` | `1` InputToken, `2` QuoteOnly, `3` both |

Missing, extra or duplicate fields and incorrect numeric types are rejected. The proposed developer ceiling must separately be approved against the target registry's protocol maximum. It is not the swap-hook fee rate.

### Hook requirements

- Derive from the chosen V1 base; preserve its typed constructor. Override only `_calculateFee`.
- Use full-precision arithmetic. Fees cannot exceed `floor(amount * maximumPips / 1_000_000)` or `int128.max`. Disclose rounding, thresholds and potential reverts.
- Preserve manager-only callbacks, mask `0x1afc` under `0x3fff`, one-time registrar binding and exact full-key checks.
- Preserve permanent liquidity custody, fee-only accounting, backing, settlement and collector-only collection. Donations are not fees.
- Preserve treasury arithmetic: `denominator == 0 ? 0 : (grossHookFee / denominator) * 125 / 100`; nonzero denominators are `4..10`.
- Preserve genuine oracle history and pre-genesis rejection. Capacity does not establish mature lookback.
- Keep developer payments in the downstream fee hub. No hook-level author payment, sweep, upgrade or recipient-selection extension.

Canonical requirements: [authoring V1](https://github.com/okjintao/black-market/blob/9fd85264d8ec0c7a509cb048e9c788d0f2b1afa4/docs/launch-hook-authoring-contract-v1.md), [admission V2](https://github.com/okjintao/black-market/blob/9fd85264d8ec0c7a509cb048e9c788d0f2b1afa4/docs/launch-hook-admission-v2.md).

## Local checks

Use Python 3.12 and Foundry `nightly-5e88010a83d1b87b8f4d13058e42a2949d3e9dc0`. Run untrusted submissions in a disposable environment without credentials or wallet keys.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r scripts/requirements.txt
python -m unittest discover -s tests
python scripts/check_hooks.py --structure-only --output evidence/structure

UPSTREAM_REPOSITORY=$(python -c 'import json; print(json.load(open("scripts/upstream.json"))["repository"])')
UPSTREAM_REVISION=$(python -c 'import json; print(json.load(open("scripts/upstream.json"))["revision"])')
git clone --no-checkout "$UPSTREAM_REPOSITORY" .integration/black-market
git -C .integration/black-market checkout --detach "$UPSTREAM_REVISION"
git -C .integration/black-market submodule update --init --recursive
python scripts/check_hooks.py --upstream .integration/black-market --output evidence/qualification
```

Clone into a dedicated checkout; use fresh evidence directories on subsequent runs. All hooks are checked. Compilation uses Solidity 0.8.28, Cancun, optimizer runs 1, no via-IR or bytecode metadata. Runtime/initcode limits are 24,576/49,152 bytes. The bound V1 reference has only 66 bytes of runtime headroom.

## PR review

Use the [PR template](.github/pull_request_template.md). Link the current Actions run and disclose missing or failed checks.

Review `PR-REVIEW.md` and `<slug>.registration-inputs.json` from the Actions artifacts. Reports separate declared inputs, file SHA256 pins, measured artifact evidence, derived registry fields and pending admission inputs. File pins are not Solidity admission digests.

CI validates input syntax/ranges and artifact behavior in the upstream fixture. It does not prove author control, execute the submitted bounds/economics, approve production policy or establish arbitrary-runtime safety. Review the complete source and executable dependency graph; record the catalogue decision against the PR commit.

Registry admission remains separate: approved artifact/review/terms commitments, target economics and deployed graph, exact envelope/profile/registration, current author-controller authorization and administrator submission. Obtain authorization using the pinned implementation's `authorizationDigest`; the upstream admission document's EIP-712 domain name differs from the implementation. Do not include private keys or admission signatures in the initial PR.
