// @flow
/* global SETTINGS: false */

import React from "react"

import MixedLink from "./MixedLink"
import { routes } from "../lib/urls"

type Props = {
  mobileView: boolean
}

const AnonymousMenu = ({ mobileView }: Props) => {
  const identifierPostfix = mobileView ? "Mobile" : "Desktop"
  const makeNavLink = (text: string) => {
    return mobileView ? (
      <span data-bs-target="#nav" data-bs-toggle="collapse">
        {text}
      </span>
    ) : (
      text
    )
  }
  return (
    <ul>
      <li>
        <MixedLink
          id="catalog"
          dest={routes.catalog}
          className="top-nav-link"
          aria-label="Catalog"
        >
          {makeNavLink("Catalog")}
        </MixedLink>
      </li>
      {SETTINGS.oidc_login_url && (
        <li>
          <MixedLink
            id={"login".concat(identifierPostfix)}
            dest={SETTINGS.oidc_login_url || ""}
            className="simple"
            aria-label="Sign In"
          >
            {makeNavLink("Sign In")}
          </MixedLink>
        </li>
      )}
      {SETTINGS.oidc_login_url && (
        <li>
          <MixedLink
            id={"createAccount".concat(identifierPostfix)}
            dest={SETTINGS.oidc_login_url || ""}
            className="simple button"
            aria-label="Create Account"
          >
            {makeNavLink("Create Account")}
          </MixedLink>
        </li>
      )}
      {!SETTINGS.oidc_login_url && SETTINGS.api_gateway_enabled && (
        <li>
          <MixedLink
            id={"login".concat(identifierPostfix)}
            dest={routes.apiGatewayLogin}
            className="simple"
            aria-label="Login"
          >
            {makeNavLink("Login")}
          </MixedLink>
        </li>
      )}
      {!SETTINGS.oidc_login_url && !SETTINGS.api_gateway_enabled && (
        <li>
          <MixedLink
            id={"login".concat(identifierPostfix)}
            dest={routes.login.begin}
            className="simple"
            aria-label="Sign In"
          >
            {makeNavLink("Sign In")}
          </MixedLink>
        </li>
      )}
      {!SETTINGS.oidc_login_url && !SETTINGS.api_gateway_enabled && (
        <li>
          <MixedLink
            id={"createAccount".concat(identifierPostfix)}
            dest={routes.register.begin}
            className="simple button"
            aria-label="Create Account"
          >
            {makeNavLink("Create Account")}
          </MixedLink>
        </li>
      )}
    </ul>
  )
}

export default AnonymousMenu
