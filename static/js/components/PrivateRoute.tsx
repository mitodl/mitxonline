import React, { ComponentType } from "react"
import { useLocation } from "react-router"
import { Redirect, Route } from "react-router-dom"
import { useCurrentUser } from "../hooks/user"
import { generateLoginRedirectUrl } from "../lib/auth"

type Props = {
  component: ComponentType<any>
  [key: string]: any
}

export default function PrivateRoute({
  component: Component,
  ...routeProps
}: Props) {
  const location = useLocation()
  const user = useCurrentUser()
  return (
    <Route
      {...routeProps}
      render={props => {
        return user && user.is_authenticated ? (
          <Component {...props} />
        ) : (
          <Redirect to={generateLoginRedirectUrl(location)} />
        )
      }}
    />
  )
}
