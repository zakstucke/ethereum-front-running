import React from "react";

import PageContainer from "apps/core/components/containers/pageContainer";

const ClientHome = () => (
  <PageContainer title="To Dos" renderTitle={false} className="text-center">
    <p className="lead">Logged in!</p>
  </PageContainer>
);

export default ClientHome;
