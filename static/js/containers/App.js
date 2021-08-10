// @flow
import React from "react"
import { compose } from "redux"
import { connect } from "react-redux"
import { Switch, Route } from "react-router"
import { connectRequest } from "redux-query"
import { createStructuredSelector } from "reselect"
import urljoin from "url-join"

import users, { currentUserSelector } from "../lib/queries/users"
import { routes } from "../lib/urls"
import { addUserNotification } from "../actions"

import Header from "../components/Header"
import PrivateRoute from "../components/PrivateRoute"

import LoginPages from "./pages/login/LoginPages"
import RegisterPages from "./pages/register/RegisterPages"
import ProfilePages from "./pages/profile/ProfilePages"
import AccountSettingsPage from "./pages/settings/AccountSettingsPage"
import EmailConfirmPage from "./pages/settings/EmailConfirmPage"
import DashboardPage from "./pages/DashboardPage"

import type { Match, Location } from "react-router"
import type { CurrentUser } from "../flow/authTypes"

type Props = {
  match: Match,
  location: Location,
  currentUser: ?CurrentUser
}

export class App extends React.Component<Props, void> {
  render() {
    const { match, currentUser, location } = this.props

    if (!currentUser) {
      // application is still loading
      return <div className="app" />
    }

    return (
      <div className="app">
        <Header currentUser={currentUser} location={location} />
        <div className="main-page-content">
          <Switch>
            <Route
              path={urljoin(match.url, String(routes.login))}
              component={LoginPages}
            />
            <Route
              path={urljoin(match.url, String(routes.register))}
              component={RegisterPages}
            />
            <PrivateRoute
              path={urljoin(match.url, String(routes.accountSettings))}
              component={AccountSettingsPage}
            />
            <PrivateRoute
              path={urljoin(match.url, String(routes.profile))}
              component={ProfilePages}
            />
            <Route
              path={urljoin(match.url, String(routes.account.confirmEmail))}
              component={EmailConfirmPage}
            />
            <PrivateRoute
              exact
              path={urljoin(match.url, String(routes.dashboard))}
              component={DashboardPage}
            />
          </Switch>
        </div>
      </div>
    )
  }
}

const mapStateToProps = createStructuredSelector({
  currentUser: currentUserSelector
})

const mapDispatchToProps = {
  addUserNotification
}

const mapPropsToConfig = () => [users.currentUserQuery()]

export default compose(
  connect(
    mapStateToProps,
    mapDispatchToProps
  ),
  connectRequest(mapPropsToConfig)
)(App)
