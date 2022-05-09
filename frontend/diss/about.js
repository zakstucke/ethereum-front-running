import React, { useState } from "react";

import PageContainer from "apps/core/components/containers/pageContainer";
import Card from "apps/core/components/card/card";
import { Button } from "apps/core/components/buttons/button";
import EarlyAccessForm from "apps/core/components/modals/earlyAccessForm";
import { contactFormOpenButtonId } from "apps/main/components/siteNavbar";

import { staticUrl } from "apps/core/index";

const founders = [
  {
    image: `${staticUrl}images/team_photos/zak.jpg`,
    title: "Zak Stucke",
    subTitle: "London, UK",
    listContent: ["Journeyman Pictures - CTO", "Computer Science (Bsc), Bristol University"],
    extraContent:
      "Zak is a veteran chief technology officer with extensive experience managing large scale infrastructure and working in fast pace environments. ",
  },
];

const About = () => {
  const [showEarlyAccessForm, setShowEarlyAccessForm] = useState(false);

  return (
    <PageContainer title="About">
      <EarlyAccessForm show={showEarlyAccessForm} setShow={setShowEarlyAccessForm} />

      <div className="text-center">
        <Button className="mx-3" size="md" onClick={() => setShowEarlyAccessForm(true)}>
          Get Early Access
        </Button>
        <Button
          className="mx-3"
          size="md"
          onClick={() => document.getElementById(contactFormOpenButtonId).click()}
        >
          Get In Touch
        </Button>
      </div>

      <hr />

      <div className="row justify-content-around">
        {founders.map((founder) => (
          <div key={founder.title} className="col-8 col-md-4 col-lg-3">
            <Card
              imageSrc={founder.image}
              title={founder.title}
              subTitle={founder.subTitle}
              listContent={founder.listContent}
              extraContent={founder.extraContent}
            />
          </div>
        ))}
      </div>
    </PageContainer>
  );
};

export default About;
