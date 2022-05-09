import React from "react";

import CONFIG from "safe_shared_config.json";
import { UNRESTRICTED, IS_AUTHENTICATED } from "apps/authentication/components/protections";

// eslint-disable-next-line no-unused-vars
const TYPES = {};

export default {
  HOME: {
    COMPONENT: React.lazy(() => import("diss/home")),
    PROTECTION_KEY: UNRESTRICTED,
    URL_DEC: CONFIG.HOME_FRONT_URL,
    BUILD_URL: () => CONFIG.HOME_FRONT_URL,
    TEXT_TO_EXPECT: "Zachary Stucke's BSc Dissertation",
    AUTO_TEST: true,
  },
  CLIENT_HOME: {
    COMPONENT: React.lazy(() => import("diss/clientHome")),
    PROTECTION_KEY: IS_AUTHENTICATED,
    URL_DEC: "/client-home",
    BUILD_URL: () => "/client-home",
    TEXT_TO_EXPECT: "Logged in!",
    AUTO_TEST: true,
  },
  ABOUT: {
    COMPONENT: React.lazy(() => import("diss/about")),
    PROTECTION_KEY: UNRESTRICTED,
    URL_DEC: CONFIG.ABOUT_FRONT_URL,
    BUILD_URL: () => CONFIG.ABOUT_FRONT_URL,
    TEXT_TO_EXPECT: "A dashboard built for Zachary Stucke's BSc Computer Science disseration.",
    AUTO_TEST: true,
  },
};
