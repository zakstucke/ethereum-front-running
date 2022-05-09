import React from "react";
import colors from "scss_global/_exports.scss";
import SectionBox from "apps/core/components/containers/sectionBox";
import { List, ListItem } from "apps/core/components/lists/list/list";
import { useGetTheme, DARK_THEME } from "apps/core/components/siteMode/siteMode";
import CONFIG from "safe_shared_config.json";

const displacementCode = `
  pragma solidity >=0.7.0 <0.9.0;

  import "@openzeppelin/contracts/utils/math/SafeMath.sol";

  contract Displacement {
    using SafeMath for uint256;

    // immutable so they cannot be changed after constructor:
    address public immutable AGENT;
    address public immutable ATTACKER;

    constructor(address agent, address attacker) {
        AGENT = agent;
        ATTACKER = attacker;
    }

    modifier onlyAllowed {
        // Allow either the agent or attacker to withdraw:
        require(msg.sender == AGENT || msg.sender == ATTACKER, "Only agent and attacker can interact!");
        _;
    }    

    // Allow receipt of funds:
    function receiveFunds() payable public {}

    function withdraw() public onlyAllowed {
        uint curBal = address(this).balance;
        require(curBal > 0, "Nothing to withdraw!");

        payable(msg.sender).transfer(curBal);
    }
  }
`;

const sandwichCode = `
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
`;

const InfoTab = () => {
  const theme = useGetTheme();

  const codeBackGroundColor =
    theme === DARK_THEME ? colors["grey-color-dark"] : colors["grey-color-very-light"];

  return (
    <div className="mt-2 text-start">
      <p>
        This dashboard was created for Zachary Stucke&apos; BSc dissertation at the University of
        Bristol.
      </p>

      <div className="mb-3">
        <p className="lead mb-1">Experiment Types</p>
        <SectionBox>
          <List>
            <ListItem key="displacement">
              <p className="primary-font">Displacement</p>
              <p>
                An environment where an attacker can identify a profitable transaction and execute
                it with their own information before the agent, thus profiting. The attacker
                monitors the pending transaction pool (mempool), simulates the transaction with
                their own information, deems it profitable and submits a replacement transaction
                with higher priority.
                <br />
                The{" "}
                <a
                  rel="noreferrer"
                  target="_blank"
                  href={`${CONFIG.ETHERSCAN_URL}/address/${CONFIG.DISPLACEMENT_ADDRESS}`}
                >
                  Holder
                </a>{" "}
                contract is used. A simple naive contract that can receive ETH; the ETH can then be
                extracted by anyone. In practice, as we don&apos;t want to be front-run ourselves,
                this is limited to the agent and attacker accounts.
                <br />
                Run on the{" "}
                <a rel="noreferrer" target="_blank" href="https://goerli.etherscan.io/">
                  Goerli testnet
                </a>
                .
              </p>
            </ListItem>
            <ListItem key="sandwich">
              <p className="primary-font">Sandwich</p>
              <p>
                An environment where an attacker can spot an agent swapping ETH for a token in a
                liquidity pool, perform their own swap before, allow the agent&apos;s transaction to
                complete and then swap back to ETH at a higher exchange rate, thus profiting. The
                attacker monitors the pending transaction pool (mempool) for transactions
                interacting with known liquidity pools.
                <br />
                The{" "}
                <a
                  rel="noreferrer"
                  target="_blank"
                  href={`${CONFIG.ETHERSCAN_URL}/address/${CONFIG.SANDWICH_ADDRESS}`}
                >
                  Pool
                </a>{" "}
                contract is used. A simple naive contract that implements a simplistic liquidity
                pool. Initially ETH is funded to the contract, which automatically sets up an
                exchange rate between ETH and the internal token. The agent and attacker can now
                swap eth for tokens and back again at a fluid exchange rate. No token spec (e.g.
                ERC20) has been implemented for simplicity; the token&apos;s are abstract and
                balances are managed internally by the contract.
                <br />
                Run on the{" "}
                <a rel="noreferrer" target="_blank" href="https://goerli.etherscan.io/">
                  Goerli testnet
                </a>
                .
              </p>
            </ListItem>
            <ListItem key="pga">
              <p className="primary-font">Priority Gas Auction (PGA)</p>
              <p>
                An environment where an attacker and an agent are both aware of one another and are
                actively bidding against each other to complete their transaction first. Actors
                incrementally outbid one another until the block is eventually mined and the last
                bid wins.
                <br />
                The{" "}
                <a
                  rel="noreferrer"
                  target="_blank"
                  href={`${CONFIG.ETHERSCAN_URL}/address/${CONFIG.DISPLACEMENT_ADDRESS}`}
                >
                  Holder
                </a>{" "}
                contract is used. A simple naive contract that can receive ETH; the ETH can then be
                extracted by anyone. In practice, as we don&apos;t want to be front-run ourselves,
                this is limited to the agent and attacker accounts.
                <br />
                Run on a locally spun{" "}
                <a rel="noreferrer" target="_blank" href="https://github.com/trufflesuite/ganache">
                  Ganache
                </a>{" "}
                blockchain emulator. Actors are actively bidding up fees to provide miners, this can
                lead to excessively high fees. I only have a limited supply of Goerli ETH available
                therefore this is run locally with fake ETH.
              </p>
            </ListItem>
          </List>
        </SectionBox>
      </div>

      <div className="mb-3">
        <p className="lead mb-1">Execution Types</p>
        <SectionBox>
          <List>
            <ListItem key="traditional">
              <p className="primary-font">Traditional</p>
              <p>
                The standard method of sending transactions to an Ethereum blockchain. The
                transaction is broadcast between Ethereum nodes and is publically visible to other
                actors before it has been mined in the transaction pool (mempool). Given the
                visibility before inclusion, this creates the front-running potential this dashboard
                attempts to depict.
              </p>
            </ListItem>
            <ListItem key="mev">
              <p className="primary-font">Flashbots Auction/MEV-geth</p>
              <p>
                A new protocol (
                <a rel="noreferrer" target="_blank" href="https://github.com/flashbots/mev-geth">
                  MEV-geth
                </a>
                ) for sending transactions to miners directly without visibility before
                mining/inclusion. Transactions are also not included if they will revert, saving the
                sender valuable fees. Created by the{" "}
                <a rel="noreferrer" target="_blank" href="https://docs.flashbots.net/">
                  Flashbots Organisation
                </a>
                .
              </p>
            </ListItem>
          </List>
        </SectionBox>
      </div>

      <div className="mb-3">
        <p className="lead mb-1">Holder Contract (Displacement and PGA)</p>
        <SectionBox style={{ backgroundColor: codeBackGroundColor }}>
          <pre className="text-start">
            <code>{displacementCode}</code>
          </pre>
        </SectionBox>
      </div>
      <div className="mb-3">
        <p className="lead mb-1">Pool Contract (Sandwich)</p>
        <SectionBox style={{ backgroundColor: codeBackGroundColor }}>
          <pre className="text-start">
            <code>{sandwichCode}</code>
          </pre>
        </SectionBox>
      </div>
    </div>
  );
};

export default InfoTab;
