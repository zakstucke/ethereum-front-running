// SPDX-License-Identifier: UNLICENSED

pragma solidity >=0.7.0 <0.9.0;

import "@openzeppelin/contracts/utils/math/SafeMath.sol";

contract Sandwich {
    using SafeMath for uint;

    address public immutable AGENT;
    address public immutable ATTACKER;

    uint public POOL_TOKEN_BALANCE = 5 * 10**17; // Funded with 0.5 eth so identical balances initially
    uint public AGENT_TOKEN_BALANCE = 0;
    uint public ATTACKER_TOKEN_BALANCE = 0;
    uint public K_VAL; // Calculated on eth funding to set curEth * POOL_TOKEN_BALANCE = K_VAL

    modifier onlyAllowed {
        require(msg.sender == AGENT || msg.sender == ATTACKER, "Only agent and attacker can interact!");
        _;
    }

    constructor(address agent, address attacker) {
        AGENT = agent;
        ATTACKER = attacker;
    }

    function updateUserTokenBal(uint newAmount) internal {
        if (msg.sender == AGENT) {
            AGENT_TOKEN_BALANCE = newAmount;
        } else {
            ATTACKER_TOKEN_BALANCE = newAmount;
        }        
    }

    // Allow receipt of funds + sets up the pool equation with the newly received eth:
    function receiveFunds() payable public {
        K_VAL = address(this).balance * POOL_TOKEN_BALANCE;
    }

    // Send eth to contract to swap with the made up internal "token":
    function swapEthForTokens() public payable onlyAllowed {
        uint newEth = msg.value;
        require(newEth > 0, "No ether sent!");

        // (newEth + curEth) * (POOL_TOKEN_BALANCE - x) = K_VAL
        uint curEth = address(this).balance;
        uint tokensOut = POOL_TOKEN_BALANCE.sub(K_VAL.div(newEth.add(curEth)));
        POOL_TOKEN_BALANCE = POOL_TOKEN_BALANCE.sub(tokensOut);
        uint oldUserTokenBal = msg.sender == AGENT ? AGENT_TOKEN_BALANCE : ATTACKER_TOKEN_BALANCE;
        updateUserTokenBal(oldUserTokenBal.add(tokensOut));
    }

    // Swap all owned made up internal "tokens" back for eth:
    function swapTokensForEth() public onlyAllowed {
        uint newTokens = msg.sender == AGENT ? AGENT_TOKEN_BALANCE : ATTACKER_TOKEN_BALANCE;
        require(newTokens >= 0, "No tokens for user to swap!");

        // (curEth - x) * (POOL_TOKEN_BALANCE + newTokens) = K_VAL
        uint curEth = address(this).balance;
        uint ethOut = curEth.sub(K_VAL.div(POOL_TOKEN_BALANCE.add(newTokens)));
        POOL_TOKEN_BALANCE = POOL_TOKEN_BALANCE.add(newTokens);
        updateUserTokenBal(0);
        payable(msg.sender).transfer(ethOut);
    }

    // Backup allow withdraw:
    function withdraw() public onlyAllowed {
        uint curEth = address(this).balance;
        require(curEth > 0, "Nothing to withdraw!");

        payable(msg.sender).transfer(curEth);
    }
}
