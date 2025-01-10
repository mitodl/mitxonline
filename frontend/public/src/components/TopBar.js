// @flow
import React, { useEffect, useState } from "react"

import { routes } from "../lib/urls"
import UserMenu from "./UserMenu"
import AnonymousMenu from "./AnonymousMenu"
import InstituteLogo from "./InstituteLogo"
import type { Location } from "react-router"
import NotificationContainer from "./NotificationContainer"

import type { CurrentUser } from "../flow/authTypes"
import MixedLink from "./MixedLink"
import { checkFeatureFlag } from "../lib/util"

type Props = {
  currentUser: CurrentUser,
  location: ?Location,
}

const TopBar = ({ currentUser }: Props) => {
  // Delay any alert displayed on page-load by 500ms in order to
  // ensure the alert is read by screen readers.
  const [showComponent, setShowComponent] = useState(false)
  useEffect(() => {
    const timeout = setTimeout(() => {
      setShowComponent(true)
    }, 500)

    return () => clearTimeout(timeout)
  }, [])

  const newCartDesign = checkFeatureFlag("new-cart-design", currentUser)
  const cartItemCount = 0
  return (
    <header className="site-header d-flex d-flex flex-column">
      {showComponent ? (
        <NotificationContainer id="notifications-container" />
      ) : null}
      <nav
        className={`order-1 sub-nav navbar navbar-expand-md top-navbar ${
          currentUser.is_authenticated ? "nowrap login" : ""
        }`}
      >
        <div className="top-branding">
          <a href="https://mitxonline.mit.edu" className="logo-link">
            <InstituteLogo />
          </a>
        </div>
        <button
          className="navbar-toggler nav-opener collapsed"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#nav"
          aria-controls="nav"
          aria-expanded="false"
          aria-label="Toggle navigation"
        >
          <span className="bar" />
          <span className="bar" />
          <span className="bar" />
        </button>
        <div
          id="nav"
          className={`${
            currentUser.is_authenticated ? "" : "collapse"
          } user-menu-overlay px-0 justify-content-end`}
        >
          <div className="full-screen-top-menu">
            {currentUser.is_authenticated ? (
              <>
                {newCartDesign ?
                  (<>
                    <button
                      className="shopping-cart-line"
                      onClick={() => (
                        window.location = routes.cart
                      )}
                      aria-label="Cart"
                    />
                    {cartItemCount ? <span className='badge' id="cart-count">{cartItemCount}</span> : null}
                    <MixedLink
                      id="catalog"
                      dest={routes.catalog}
                      className="top-nav-link border-left-top-bar"
                      aria-label="Catalog"
                    >
                        Catalog
                    </MixedLink></>
                  ) : (
                    <MixedLink
                      id="catalog"
                      dest={routes.catalog}
                      className="top-nav-link"
                      aria-label="Catalog"
                    >
                    Catalog
                    </MixedLink>
                  )
                }
                <UserMenu currentUser={currentUser} useScreenOverlay={false}/>
              </>
            ) : (
              <AnonymousMenu mobileView={false} />
            )}
          </div>
          <div className="mobile-auth-buttons">
            {currentUser.is_authenticated ? (
              <UserMenu currentUser={currentUser} useScreenOverlay={true} />
            ) : (
              <AnonymousMenu mobileView={true} />
            )}
          </div>
        </div>
      </nav>
    </header>
  )
}

export default TopBar
