import React from "react";

import Icon from "apps/core/components/icons/icon";
import colors from "scss_global/_exports.scss";

// eslint-disable-next-line import/prefer-default-export
export const renderBalanceChange = (text, change) => {
  let color;
  let iconKey;
  if (change >= 0.001) {
    color = colors["success-color"];
    iconKey = "arrowUp";
  } else if (change < -0.001) {
    color = colors["failure-color"];
    iconKey = "arrowDown";
  } else {
    color = colors["success-color"];
    iconKey = "tick";
  }
  return (
    <span style={{ color }}>
      {text}
      <Icon iconKey={iconKey} color={color} size={15} />
    </span>
  );
};
