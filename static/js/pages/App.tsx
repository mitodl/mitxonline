import React from "react"
import { Route } from "react-router"

export default function App(): JSX.Element {
  return (
    <div className="app">
      <Route path="/" render={() => <div>Hello cookiecutter!</div>} />
    </div>
  )
}
