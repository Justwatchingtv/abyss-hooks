// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import { FixedPointMathLib } from "solady/utils/FixedPointMathLib.sol";
import { IPoolManager } from "@uniswap/v4-core/src/interfaces/IPoolManager.sol";
import { IAbyssLaunchFactory } from "@black-market/interfaces/IAbyssLaunch.sol";
import { SharedLaunchHookBaseV1 } from "@black-market/hooks/v4/authoring/SharedLaunchHookBaseV1.sol";

/// @notice CI reference schedule, not an admitted production hook.
contract ReferenceSharedHook is SharedLaunchHookBaseV1 {
    constructor(IPoolManager manager, address registrar, IAbyssLaunchFactory oracleFactory)
        SharedLaunchHookBaseV1(manager, registrar, oracleFactory) { }

    function _calculateFee(uint256 amount, uint24 maximumPips)
        internal pure override returns (uint256)
    {
        return FixedPointMathLib.fullMulDiv(amount, maximumPips, PIPS_DENOMINATOR);
    }
}
