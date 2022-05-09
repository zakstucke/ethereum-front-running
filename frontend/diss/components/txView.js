import React, { useState } from "react";
import { API_URLS } from "apps/core/urlRoot";
import useGenericRequest from "apps/core/api/genericRequest";
import { List, ListItem } from "apps/core/components/lists/list/list";
import LoaderBoundary from "apps/core/components/loaders/loaderBoundary/loaderBoundary";
import Icon from "apps/core/components/icons/icon";
import GeneralModal from "apps/core/components/modals/generalModal";
import { FixedTableGraph } from "apps/main/components/graphs/tableGraph";
import CheckBox from "apps/core/components/form/checkbox";
import colors from "scss_global/_exports.scss";
import CONFIG from "safe_shared_config.json";

import { renderBalanceChange } from "diss/utils";

const TxView = () => {
  const refetchAfterSeconds = 3;
  const txReq = useGenericRequest(API_URLS.GET_TXS.URL, "GET", {
    instant: true,
    pageCache: true,
    refetchAfterSeconds,
  });

  const [showModal, setShowModal] = useState(false);
  const [activeItemInfo, setActiveItemInfo] = useState(null);
  const [filterCompletedTxs, setFilterCompletedTxs] = useState(false);
  const [onlyLastExperiment, setOnlyLastExperiment] = useState(true);

  const statusIcon = (status) => {
    const iconSize = 15;
    let icon;
    if (status === "success") {
      icon = <Icon iconKey="tick" size={iconSize} />;
    } else if (status === "pending") {
      icon = <Icon iconKey="questionMark" size={iconSize} />;
    } else {
      icon = <Icon iconKey="cross" size={iconSize} />;
    }

    return icon;
  };

  const identifyAddress = (address) => {
    if (address.toUpperCase() === CONFIG.AGENT_ADDRESS.toUpperCase()) {
      return <span style={{ color: "blue" }}>AGENT</span>;
    }
    if (address.toUpperCase() === CONFIG.ATTACKER_ADDRESS.toUpperCase()) {
      return <span style={{ color: "red" }}>ATTACKER</span>;
    }
    return <span style={{ color: "grey" }}>OTHER</span>;
  };

  const renderExplorer = (itemInfo) => {
    if (itemInfo.node_url.includes("127.0.0.1")) {
      return <p className="mb-0">Cannot view local Ganache blockchain txs on explorer.</p>;
    }
    if (["success", "reverted"].includes(itemInfo.status)) {
      return (
        <a
          rel="noreferrer"
          target="_blank"
          href={`${CONFIG.ETHERSCAN_URL}/tx/${activeItemInfo.hash}`}
          className="small-text-link"
        >
          View on explorer
          <Icon color={colors["primary-color"]} iconKey="arrowRight" size={20} />
        </a>
      );
    }
    return <p className="mb-0">Can only view successful or reverted transactions on explorer.</p>;
  };

  return (
    <>
      {activeItemInfo ? (
        <GeneralModal title="TX" size="xl" show={!!showModal} setShow={setShowModal}>
          <div className="text-center">{renderExplorer(activeItemInfo)}</div>
          <FixedTableGraph
            data={Object.keys(activeItemInfo).map((key) => ({
              label: key.replace("_", " ").replace(/(^\w|\s\w)/g, (m) => m.toUpperCase()),
              value: activeItemInfo[key],
            }))}
            cellsPerLine={3}
            animate={false} // Starts hidden so don't want to animate (animate on enter hook doesn't work for this situ)
          />
        </GeneralModal>
      ) : null}

      <h3 className="mt-3">Transaction Log</h3>
      <small className="primary-text-color">
        Click a TX for more information & view on explorer.
        <br />
        Refreshes every {refetchAfterSeconds} seconds. {txReq.loading ? "Loading..." : ""}
        <br />
        <CheckBox
          id="filter-last-experiment"
          name="filter-last-experiment"
          checked={onlyLastExperiment}
          onChange={() => setOnlyLastExperiment(!onlyLastExperiment)}
          label="Last experiment only"
        />
        <CheckBox
          id="filter-completed-txs"
          name="filter-completed-txs"
          checked={filterCompletedTxs}
          onChange={() => setFilterCompletedTxs(!filterCompletedTxs)}
          label="Filter only completed txs"
        />
      </small>

      <LoaderBoundary requests={[txReq]}>
        {() => {
          const mostRecentExperimentPk = txReq.response.txs
            ? txReq.response.txs[0].experiment_pk
            : "";
          const mostRecentExperimentDesc = txReq.response.txs
            ? txReq.response.txs[0].experiment
            : "";
          const mostRecentExperimentFinished = txReq.response.txs
            ? txReq.response.txs[0].experiment_finished
            : false;
          const mostRecentExperimentAgentChange = txReq.response.txs
            ? txReq.response.txs[0].experiment_agent_balance_change
            : 0;
          const mostRecentExperimentAttackerChange = txReq.response.txs
            ? txReq.response.txs[0].experiment_attacker_balance_change
            : 0;

          const items = txReq.response.txs.map((itemInfo) => {
            if (!onlyLastExperiment || itemInfo.experiment_pk === mostRecentExperimentPk) {
              if (!filterCompletedTxs || ["success", "reverted"].includes(itemInfo.status)) {
                return (
                  <ListItem
                    key={`${itemInfo.pk}`} // Can be an integer
                    onClick={() => {
                      setShowModal(true);
                      setActiveItemInfo(itemInfo);
                    }}
                  >
                    <p className="small mb-0">{identifyAddress(itemInfo.account_address)}</p>
                    <p className="small mb-0">Info: {itemInfo.description}</p>
                    <p className="small mb-0">
                      {statusIcon(itemInfo.status)}
                      {itemInfo.status}
                    </p>
                    <p className="small mb-0">Priority fee: {itemInfo.priority_gas}</p>
                    <p className="small mb-0">{itemInfo.last_sent}</p>
                  </ListItem>
                );
              }
            }

            return null;
          });

          if (onlyLastExperiment && mostRecentExperimentFinished) {
            items.unshift(
              <ListItem key="experiment-finished">
                <p className="mb-0">
                  Experiment Finished!
                  <br />
                  Outcome:
                  <br />
                  <span>
                    {renderBalanceChange(
                      `Agent: ${mostRecentExperimentAgentChange.toFixed(3)}`,
                      mostRecentExperimentAgentChange,
                    )}
                    {renderBalanceChange(
                      `Attacker: ${mostRecentExperimentAttackerChange.toFixed(3)}`,
                      mostRecentExperimentAttackerChange,
                    )}
                  </span>
                </p>
              </ListItem>,
            );
          }

          if (onlyLastExperiment && mostRecentExperimentDesc) {
            items.push(
              <ListItem key="experiment-desc">
                <p className="mb-0">{mostRecentExperimentDesc}</p>
              </ListItem>,
            );
          }

          return (
            <>
              <List>{items}</List>
              {!onlyLastExperiment && items.length >= 30 ? (
                <p>Only showing the last 30 transactions.</p>
              ) : null}
            </>
          );
        }}
      </LoaderBoundary>
    </>
  );
};

export default TxView;
