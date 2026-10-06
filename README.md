# abyss-hooks

Community Uniswap V4 launch hooks for Black Market. Submit hooks through pull requests.

## Supported hooks

| Topology | Base | Example |
| --- | --- | --- |
| Shared | `SharedLaunchHookBaseV1` | [reference-shared](hooks/reference-shared) |
| Pool-bound | `PoolBoundLaunchHookBaseV1` | [reference-bound](hooks/reference-bound) |

The current contribution interface is a pure fee schedule:

```solidity
function _calculateFee(uint256 amount, uint24 maximumPips)
    internal pure override returns (uint256);
```

Retain the base constructor and outer behavior. Callback redesigns and V2 / Surge hooks are outside the current scope.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for required files, input validation and local commands.

Every PR checks the entire catalogue:

- **Hook structure:** submission fields, registry bounds and validator tests.
- **Hook qualification:** pinned upstream build, independent compiler reconstruction, size limits, real-manager tests and headless lifecycle execution.

Actions provides an input-review summary and downloadable registration-input reports and runtime logs. The upstream revision is pinned in [scripts/upstream.json](scripts/upstream.json).

Passing CI or merging a hook does not register it. Registry admission requires separate source/runtime review, approved economics, deployment provenance, author-controller consent and administrator registration.

## Maintainer setup

Enable Actions and require **Hook structure**, **Hook qualification** and PR review through branch protection or a ruleset. Review tooling, workflow and upstream-pin changes separately from hook submissions. Fork jobs must remain on disposable hosted runners without secrets, persisted credentials or broadcasting.

## Licensing

Each hook declares its SPDX license. Preserve dependency notices and verify that you have the rights to contribute the source.
