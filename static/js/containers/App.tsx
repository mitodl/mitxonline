import React, { useEffect } from "react"
import { Route, Switch, useRouteMatch } from "react-router"
import { useRequest } from "redux-query-react"
import urljoin from "url-join"
import Header from "../components/Header"
import PrivateRoute from "../components/PrivateRoute"
import { useNotifications } from "../hooks/notifications"
import useTracker from "../hooks/tracker"
import { useCurrentUser } from "../hooks/user"
import {
  getStoredUserMessage,
  removeStoredUserMessage
} from "../lib/notificationsApi"
import { currentUserQuery } from "../lib/queries/users"
import { routes } from "../lib/urls"
import DashboardPage from "./pages/DashboardPage"
import LoginPages from "./pages/login/LoginPages"
import EditProfilePage from "./pages/profile/EditProfilePage"
import RegisterPages from "./pages/register/RegisterPages"
import AccountSettingsPage from "./pages/settings/AccountSettingsPage"
import EmailConfirmPage from "./pages/settings/EmailConfirmPage"

export default function App() {
  const match = useRouteMatch()
  const currentUser = useCurrentUser()
  const { addNotification } = useNotifications()

  useRequest(currentUserQuery())

  useTracker()

  useEffect(() => {
    const userMsg = getStoredUserMessage()

    if (userMsg) {
      addNotification("loaded-user-msg", {
        type:  userMsg.type,
        props: {
          text: userMsg.text
        }
      })
      removeStoredUserMessage()
    }
  }, [])

  if (!currentUser) {
    // application is still loading
    return <div className="app" />
  }

  return (
    <div className="app">
      <Header currentUser={currentUser} />
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
        </Switch>
      </div>
    </div>
  )
}
