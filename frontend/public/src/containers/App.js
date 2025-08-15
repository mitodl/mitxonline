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
import LoginSso from "./pages/login/LoginSso"
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
import {
  cartItemsCountQuery,
  cartItemsCountSelector
} from "../lib/queries/cart"
import RegisterDetailsPage from "./pages/register/new_RegisterDetailsPage"
import RegisterAdditionalDetailsPage from "./pages/register/new_RegisterAdditionalDetailsPage"

type Props = {
  match: Match,
  location: Location,
  currentUser: ?CurrentUser,
  cartItemsCount: number,
  addUserNotification: Function,
  forceRequest: Function
}

export class App extends React.Component<Props, void> {
  componentDidMount() {
    const { addUserNotification } = this.props

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

  componentDidUpdate(prevProps: Props) {
    const { currentUser, forceRequest } = this.props

    // If user just loaded and is authenticated, fetch cart items count
    if (!prevProps.currentUser && currentUser && currentUser.is_authenticated) {
      forceRequest(cartItemsCountQuery())
    }
  }

  render() {
    const { match, currentUser, cartItemsCount, location } = this.props
    if (!currentUser) {
      // application is still loading
      return <div className="app" />
    }

    return (
      <div className="app" aria-flowto="notifications-container">
        <Header
          currentUser={currentUser}
          cartItemsCount={currentUser.is_authenticated ? cartItemsCount : 0}
          location={location}
        />
        <div id="main" className="main-page-content">
          <Switch>
            <Route
              path={urljoin(match.url, String(routes.login))}
              component={LoginPages}
            />
            <Route
              path={urljoin(match.url, String(routes.apiGatewayLogin))}
              component={LoginSso}
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
            <PrivateRoute
              path={urljoin(match.url, String(routes.create_profile))}
              component={RegisterDetailsPage}
            />
            <PrivateRoute
              path={urljoin(match.url, String(routes.create_profile_extra))}
              component={RegisterAdditionalDetailsPage}
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
              path={urljoin(match.url, String(routes.catalogTabByDepartment))}
              component={CatalogPage}
            />
            <Route
              path={urljoin(match.url, String(routes.catalogTab))}
              component={CatalogPage}
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
  currentUser:    currentUserSelector,
  cartItemsCount: cartItemsCountSelector
})

const mapDispatchToProps = {
  addUserNotification
}

const mapPropsToConfig = () => [users.currentUserQuery()]
export default compose(
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(App)
