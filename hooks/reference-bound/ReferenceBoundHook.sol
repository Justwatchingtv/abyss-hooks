// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import { FixedPointMathLib } from "solady/utils/FixedPointMathLib.sol";
import { PoolBoundHookParametersV1 } from "@black-market/hooks/v4/PoolBoundHookParametersV1.sol";
import { PoolBoundLaunchHookBaseV1 } from "@black-market/hooks/v4/authoring/PoolBoundLaunchHookBaseV1.sol";

/// @notice CI reference schedule, not an admitted production hook.
contract ReferenceBoundHook is PoolBoundLaunchHookBaseV1 {
    constructor(PoolBoundHookParametersV1 memory parameters) PoolBoundLaunchHookBaseV1(parameters) { }

    function _calculateFee(uint256 amount, uint24 maximumPips)
        internal pure override returns (uint256)
    {
        return FixedPointMathLib.fullMulDiv(amount, maximumPips, PIPS_DENOMINATOR);
    }
}
