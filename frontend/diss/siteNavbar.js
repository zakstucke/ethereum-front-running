import React, { useState } from "react";

import Navbar from "react-bootstrap/Navbar";
import { Dropdown, DropdownItem } from "apps/core/components/dropdowns/dropdown";
import PropTypes from "prop-types";
import Nav from "react-bootstrap/Nav";

import { useAuth, useLogout } from "apps/authentication/logicOnly/authentication";

import { FRONT_URLS } from "apps/core/urlRoot";

import NavLink from "apps/core/components/nav/navLink";
import styles from "apps/core/components/nav/nav.scss";
import ContactForm from "apps/core/components/modals/contactForm";

import Logo from "apps/core/components/images/logo_square";
import { useLocation, useNavigate } from "react-router-dom";

export const contactFormOpenButtonId = "contact-form-show-button";

const SiteNavbar = ({ siteMode }) => {
  const logout = useLogout();

  const [contactFormShow, setContactFormShow] = useState(false);

  const auth = useAuth();

  const location = useLocation();
  const navigate = useNavigate();

  return (
    <>
      <ContactForm show={contactFormShow} setShow={setContactFormShow} />

      <Navbar
        expand="md"
        className={styles["site-header"]}
        onToggle={(isOpen) => {
          if (isOpen) {
            let isFirstClick = true;
            document.addEventListener("click", function namedListener(e) {
              // Want to still be able to open dropdowns) {
              if (isFirstClick || e.target.classList.contains("dropdown-toggle")) {
                // First click is the initial open therefore don't want to count it
                isFirstClick = false;
              } else {
                if (!document.getElementById("site-navbar-toggle").contains(e.target)) {
                  document.getElementById("site-navbar-toggle").click();
                }
                document.removeEventListener("click", namedListener);
              }
            });
          }
        }}
      >
        <div className="container-fluid">
          {/* Using this method as it allows the home url link to be inside of the Nav component, this helps with active classes etc */}
          <Navbar.Brand
            aria-label="Home"
            as={Nav.Link}
            className={`mx-2 my-1 ${styles["real-link"]}`}
            onClick={() => {
              // If already on the home page, actually refresh the page:
              if (location.pathname === FRONT_URLS.HOME.BUILD_URL()) {
                window.location.reload();
              } else {
                // Otherwise normal link to home:
                document.getElementById("hidden-home-link").click();
              }
            }}
          >
            <Logo alt="Logo" width="80" className="d-inline-block align-top" />
          </Navbar.Brand>

          <Navbar.Toggle aria-controls="responsive-navbar-nav" id="site-navbar-toggle">
            <div className={styles.holder}>
              <div className={styles.hamburger}>
                <span />
                <span />
                <span />
              </div>
              <div className={styles.cross}>
                <span />
                <span />
              </div>
            </div>
          </Navbar.Toggle>

          <Navbar.Collapse id="responsive-navbar-nav">
            <Nav className="flex-grow-1">
              <div className="navbar-nav">
                <button
                  type="button"
                  id="hidden-home-link"
                  className="hidden"
                  onClick={() => navigate(FRONT_URLS.HOME.BUILD_URL())}
                >
                  Home Link
                </button>

                {auth.loggedIn ? (
                  <>
                    <NavLink>Hello {auth.userDetails.first_name}!</NavLink>
                    <NavLink
                      url={FRONT_URLS.HOME.BUILD_URL()}
                      onClick={() => logout()}
                      checkIfActive={false} // Is not a page link, just happens to redirect to home
                    >
                      Logout
                    </NavLink>
                  </>
                ) : (
                  <>
                    <NavLink url={FRONT_URLS.LOGIN_SIGNUP.BUILD_URL("login")}> Login</NavLink>
                    <NavLink url={FRONT_URLS.LOGIN_SIGNUP.BUILD_URL("signup")}> Signup</NavLink>
                  </>
                )}
              </div>

              <div className="navbar-nav" id={styles["pulled-right-navbar"]}>
                <NavLink id={contactFormOpenButtonId} onClick={() => setContactFormShow(true)}>
                  Contact
                </NavLink>

                <Dropdown
                  toggleLabel="Info"
                  className={styles.dropdown}
                  toggleProps={{ className: ` nav-link no-styling` }}
                  toggleAs="button"
                >
                  <DropdownItem
                    onClick={() => navigate(FRONT_URLS.ABOUT.BUILD_URL())}
                    className={styles["real-link"]}
                    active={location.pathname === FRONT_URLS.ABOUT.BUILD_URL()}
                  >
                    About
                  </DropdownItem>
                  <DropdownItem
                    onClick={() => navigate(FRONT_URLS.STYLING.BUILD_URL())}
                    className={styles["real-link"]}
                    active={location.pathname === FRONT_URLS.STYLING.BUILD_URL()}
                  >
                    Styling
                  </DropdownItem>
                </Dropdown>

                {auth.loggedIn ? (
                  <Dropdown
                    toggleLabel="Account"
                    className={styles.dropdown}
                    toggleProps={{ className: ` nav-link no-styling` }}
                    toggleAs="button"
                  >
                    <DropdownItem
                      onClick={() => navigate(FRONT_URLS.CLIENT_HOME.BUILD_URL())}
                      className={styles["real-link"]}
                      active={location.pathname === FRONT_URLS.CLIENT_HOME.BUILD_URL()}
                    >
                      Client Home
                    </DropdownItem>
                    <DropdownItem
                      onClick={() => navigate(FRONT_URLS.PROFILE.BUILD_URL())}
                      className={styles["real-link"]}
                      active={location.pathname === FRONT_URLS.PROFILE.BUILD_URL()}
                    >
                      Profile
                    </DropdownItem>
                  </Dropdown>
                ) : null}

                <Nav.Link
                  onClick={siteMode.onClick}
                  className={`${styles["real-link"]} px-3 ${styles["site-mode"]}`}
                >
                  {siteMode.comp}
                </Nav.Link>
              </div>
            </Nav>
          </Navbar.Collapse>
        </div>
      </Navbar>
    </>
  );
};

SiteNavbar.propTypes = {
  siteMode: PropTypes.any,
};

export default SiteNavbar;
