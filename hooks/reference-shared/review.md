# ReferenceSharedHook

- Base: `SharedLaunchHookBaseV1`; shared root with full-PoolId-indexed state.
- Fee: `floor(amount * maximumPips / 1_000_000)`, using full-precision arithmetic.
- Changes: fee calculation only; constructor and outer behavior unchanged. No added storage, selectors, authority or external calls.
- Integration: reference only; no author identity or proposed developer allocation. Bounds declare the canonical registry range, not exhaustive test coverage.
- Risks: inherited code/dependencies and schedule liveness require review.
- License: MIT; dependency licenses remain applicable.
