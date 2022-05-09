import React from "react";
import { API_URLS } from "apps/core/urlRoot";
import Form from "apps/core/components/form/form";
import HelpTip from "apps/core/components/overlays/helpTip";

const SimForm = () => {
  const fields = [
    {
      caption: "Simulation Type",
      name: "sim_type",
      type: "dropdown",
      options: [
        {
          caption: "Displacement",
          name: "displacement",
          helpTip: "An attacker attempts to front-run a profitable transaction.",
        },
        {
          caption: "Sandwich",
          name: "sandwich",
          helpTip:
            "An attacker both front and back-runs as swap transaction to a simplified liquidity pool.",
        },
        {
          caption: "Priority Gas Auction (Ganache)",
          name: "pga",
          helpTip:
            "The agent and attacker compete to complete their transaction first by bidding up the priority fees.",
        },
      ],
      required: true,
      initialValue: false,
    },
    {
      caption: "Execution Type",
      name: "execution_type",
      type: "dropdown",
      options: [
        {
          caption: "Traditional",
          name: "traditional",
          helpTip: "Transactions enter the mempool and are visible to the attacker.",
        },
        {
          caption: "Flashbots Auction/MEV-geth",
          name: "mev",
          helpTip: "Uses the modified MEV-geth protocol: the attacker cannot see transactions.",
        },
      ],
      required: true,
      initialValue: false,
    },
  ];

  return (
    <div className="text-start no-form-border">
      <span className="position-absolute">
        <HelpTip
          className="px-1"
          bodyContent={<p className="mb-0">Click the info tab to learn more.</p>}
        />
      </span>
      <Form
        showServerResponse
        submitUrl={API_URLS.RUN_SIMULATION.URL}
        formFields={fields}
        key="sim-form"
        formId="sim-form"
        formTitle="Initiate Experiment" // Shown on page instead
        submitButtonName="Run"
        extraContentTop={
          <div className="text-start">
            <small>
              Choose the type of experiment and the method the agent should use to send
              transactions.
              <br />
              Note: accounts must send transactions sequentially so if an experiment is already
              running, this form will reject the request.
            </small>
          </div>
        }
      />
    </div>
  );
};

export default SimForm;
