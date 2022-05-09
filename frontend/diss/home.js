import React from "react";

import PageContainer from "apps/core/components/containers/pageContainer";
import { Button, buttonStates } from "apps/core/components/buttons/button";
import SectionBox from "apps/core/components/containers/sectionBox";
import useBackendGraphs from "apps/main/components/graphs/useBackendGraphs";
import { API_URLS } from "apps/core/urlRoot";
import HelpTip from "apps/core/components/overlays/helpTip";
import CONFIG from "safe_shared_config.json";
import Icon from "apps/core/components/icons/icon";
import { Tab, TabHolder } from "apps/core/components/tabs/tabs";
import colors from "scss_global/_exports.scss";

import InfoTab from "diss/components/infoTab";
import TxView from "diss/components/txView";
import SimForm from "diss/components/simForm";
import { renderBalanceChange } from "diss/utils";

const Home = () => {
  const sectionHeight = 400;

  const balanceGraphs = useBackendGraphs(API_URLS.BALANCES.URL, {});

  let agentChange;
  let attackerChange;
  if (balanceGraphs.response.accepted) {
    const graphData = balanceGraphs.response.data[0].config.data;
    agentChange = graphData[0].slice("-1")[0][1] - graphData[0][0][1];
    attackerChange = graphData[1].slice("-1")[0][1] - graphData[1][0][1];
  }

  return (
    <PageContainer title="Home" renderTitle={false} className="text-center">
      <TabHolder openingTabEventKey="dashboard">
        <Tab eventKey="dashboard" title="Dashboard">
          <div className="mt-2">
            <div className="row">
              <div className="col">
                <SectionBox height={sectionHeight} className="mb-3 container-sm">
                  <SimForm />
                </SectionBox>
              </div>
              <div className="col">
                <SectionBox height={sectionHeight} className="mb-3 container-sm">
                  <TxView />
                </SectionBox>
              </div>
            </div>

            <SectionBox height={sectionHeight} className="mb-3 container-sm">
              <div>
                <HelpTip
                  className="px-1"
                  titleText="What is this?"
                  bodyContent={
                    <p className="mb-0">
                      Transactions for each account are polled over the last hour. Balances are then
                      calculated for the block height of each transaction; the balances at the start
                      and end of the period are also shown.
                      <br />
                      Note: this is for the Goerli network only.
                    </p>
                  }
                />
                <a
                  rel="noreferrer"
                  target="_blank"
                  href={`${CONFIG.ETHERSCAN_URL}/address/${CONFIG.AGENT_ADDRESS}`}
                  className="small-text-link mx-1"
                >
                  View Agent
                  <Icon color={colors["primary-color"]} iconKey="arrowRight" size={20} />
                </a>
                <a
                  rel="noreferrer"
                  target="_blank"
                  href={`${CONFIG.ETHERSCAN_URL}/address/${CONFIG.ATTACKER_ADDRESS}`}
                  className="small-text-link mx-1"
                >
                  View Attacker
                  <Icon color={colors["primary-color"]} iconKey="arrowRight" size={20} />
                </a>
              </div>
              {balanceGraphs.render()}
              {agentChange && attackerChange ? (
                <span>
                  {renderBalanceChange(`Agent: ${agentChange.toFixed(3)}`, agentChange)}
                  {renderBalanceChange(`Attacker: ${attackerChange.toFixed(3)}`, attackerChange)}
                </span>
              ) : null}
            </SectionBox>
            <div className="mb-2">
              <Button
                size="sm"
                status={balanceGraphs.loading ? buttonStates.LOADING : buttonStates.ACTIONABLE}
                onClick={() => balanceGraphs.refire()}
              >
                Refresh Balances
              </Button>
            </div>
          </div>
        </Tab>
        <Tab eventKey="info" title="Info">
          <InfoTab />
        </Tab>
      </TabHolder>
    </PageContainer>
  );
};

export default Home;
