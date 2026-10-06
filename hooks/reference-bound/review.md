# ReferenceBoundHook

- Base: `PoolBoundLaunchHookBaseV1`; one exact pool key per instance.
- Fee: `floor(amount * maximumPips / 1_000_000)`, using full-precision arithmetic.
- Changes: fee calculation only; constructor and outer behavior unchanged. No added storage, selectors, authority or external calls.
- Integration: reference only; no author identity or proposed developer allocation. Bounds declare the canonical registry range, not exhaustive test coverage.
- Risks: inherited code/dependencies and schedule liveness require review. Bound V1 runtime size leaves little room for additional logic.
- License: MIT; dependency licenses remain applicable.
