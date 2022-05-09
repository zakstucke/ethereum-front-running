// SPDX-License-Identifier: UNLICENSED

pragma solidity >=0.7.0 <0.9.0;

import "@openzeppelin/contracts/utils/math/SafeMath.sol";

contract TestContract {
    using SafeMath for uint256;

    address public immutable DEPLOYER; // immutable so cannot be changed after construction.

    uint storeVal = 0;

    constructor() {
        DEPLOYER = msg.sender;
    }

    function retrieve() public view returns (uint) {
        return storeVal;
    }

    function store(uint newVal) public {
        require(newVal != 999, "Cannot be 999!");

        storeVal = newVal;
    }
}
