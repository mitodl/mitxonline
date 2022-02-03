import React from "react"
import { Route, Switch } from "react-router-dom"
import { routes } from "../../../lib/urls"
import LoginEmailPage from "./LoginEmailPage"
import LoginForgotPasswordConfirmPage from "./LoginForgotPasswordConfirmPage"
import LoginForgotPasswordPage from "./LoginForgotPasswordPage"
import LoginPasswordPage from "./LoginPasswordPage"

const ForgotPasswordPages = () => (
  <React.Fragment>
    <Route
      exact
      path={routes.login.forgot.begin}
      component={LoginForgotPasswordPage}
    />
    <Route
      exact
      path={routes.login.forgot.confirm}
      component={LoginForgotPasswordConfirmPage}
    />
  </React.Fragment>
)

const LoginPages = () => (
  <Switch>
    <Route exact path={routes.login.begin} component={LoginEmailPage} />
    <Route exact path={routes.login.password} component={LoginPasswordPage} />
    <Route
      path={routes.login.forgot.toString()}
      component={ForgotPasswordPages}
    />
  </Switch>
)

export default LoginPages
