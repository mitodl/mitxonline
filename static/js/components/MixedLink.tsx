import React, { ReactNode } from "react"
import { Link } from "react-router-dom"
import { AppTypeContext, SPA_APP_CONTEXT } from "../contextDefinitions"

type Props = {
  children: ReactNode | ReactNode[]
  dest: string
  [key: string]: any
}

export default function MixedLink({ children, dest, ...otherProps }: Props) {
  return (
    <AppTypeContext.Consumer>
      {appType =>
        appType === SPA_APP_CONTEXT ? (
          <Link to={dest} {...otherProps}>
            {children}
          </Link>
        ) : (
          <a href={dest} {...otherProps}>
            {children}
          </a>
        )
      }
    </AppTypeContext.Consumer>
  )
}
