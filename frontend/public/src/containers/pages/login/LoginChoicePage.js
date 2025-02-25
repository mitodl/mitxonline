// @flow
/* global SETTINGS: false */
import React from "react"
import DocumentTitle from "react-document-title"
import { LOGIN_EMAIL_PAGE_TITLE } from "../../../constants"
import { compose } from "redux"
import { connect } from "react-redux"

import { routes, getNextParam } from "../../../lib/urls"

import type { RouterHistory, Location } from "react-router"

import { Link } from "react-router-dom"

type Props = {
  location: Location,
  history: RouterHistory,
}

export class LoginChoicePage extends React.Component<Props> {
  render() {
    if (!SETTINGS.oidc_login_url) {
      this.props.history.push(routes.login.email)
    }

    return (
      <DocumentTitle
        title={`${SETTINGS.site_name} | ${LOGIN_EMAIL_PAGE_TITLE}`}
      >
        <div className="std-page-body container auth-page">
          <div className="std-card std-card-auth">
            <div className="std-card-body">
              <h1>Sign in</h1>

              <div>
                <Link
                  to={routes.login.email}
                  className="btn btn-primary btn-gradient-red-to-blue large w-100"
                >
                  Sign In with Email
                </Link>
              </div>
              <div>
                <a
                  href={SETTINGS.oidc_login_url}
                  className="btn btn-secondary btn-gradient-red-to-blue large w-100"
                >
                  Sign In with Keycloak
                </a>
              </div>
            </div>
          </div>
        </div>
      </DocumentTitle>
    )
  }
}

const mapDispatchToProps = {
}

export default compose(connect(null, mapDispatchToProps))(LoginChoicePage)
