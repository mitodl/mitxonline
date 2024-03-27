// @flow
import React from "react"
import { compose } from "redux"
import { connect } from "react-redux"
import { Switch, Route } from "react-router"
import { connectRequest } from "redux-query-react"
import { createStructuredSelector } from "reselect"
import urljoin from "url-join"

import users, { currentUserSelector } from "../lib/queries/users"
import { routes } from "../lib/urls"
import {
  getStoredUserMessage,
  removeStoredUserMessage
} from "../lib/notificationsApi"
import { addUserNotification } from "../actions"

import Header from "../components/Header"
import PrivateRoute from "../components/PrivateRoute"

import LoginPages from "./pages/login/LoginPages"
import RegisterPages from "./pages/register/RegisterPages"
import EditProfilePage from "./pages/profile/EditProfilePage"
import AccountSettingsPage from "./pages/settings/AccountSettingsPage"
import EmailConfirmPage from "./pages/settings/EmailConfirmPage"
import DashboardPage from "./pages/DashboardPage"
import CartPage from "./pages/checkout/CartPage"
import OrderHistory from "./pages/checkout/OrderHistory"
import OrderReceiptPage from "./pages/checkout/OrderReceiptPage"
import LearnerRecordsPage from "./pages/records/LearnerRecordsPage"
import CatalogPage from "./pages/CatalogPage"

import type { Match, Location } from "react-router"
import type { CurrentUser } from "../flow/authTypes"

type Props = {
  match: Match,
  location: Location,
  currentUser: ?CurrentUser,
  addUserNotification: Function
}

export class App extends React.Component<Props, void> {
  componentDidMount() {
    const { addUserNotification } = this.prop

    const userMsg = getStoredUserMessage()
    if (userMsg) {
      addUserNotification({
        "loaded-user-msg": {
          type:  userMsg.type,
          props: {
            text: userMsg.text
          }
        }
      })
      removeStoredUserMessage()
    }
  }

  render() {
    const { match, currentUser, location } = this.props
    if (!currentUser) {
      // application is still loading
      return <div className="app" />
    }

    return (
      <div className="app" aria-flowto="notifications-container">
        <Header currentUser={currentUser} location={location} />
        <div id="main" className="main-page-content">
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
              component={EditProfilePage}
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
            <Route
              path={urljoin(match.url, String(routes.cart))}
              component={CartPage}
            />
            <Route
              path={urljoin(match.url, String(routes.sharedLearnerRecord))}
              component={LearnerRecordsPage}
            />
            <PrivateRoute
              path={urljoin(match.url, String(routes.orderHistory))}
              component={OrderHistory}
            />
            <PrivateRoute
              path={urljoin(match.url, String(routes.orderReceipt))}
              component={OrderReceiptPage}
            />
            <PrivateRoute
              path={urljoin(match.url, String(routes.learnerRecords))}
              component={LearnerRecordsPage}
            />
            <Route
              path={urljoin(match.url, String(routes.catalog))}
              component={CatalogPage}
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
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(App)
