// @flow
/* global SETTINGS: false */

// From https://github.com/ReactTraining/react-router/issues/4278#issuecomment-299692502
import React from "react"
import ReactGA from "react-ga4"

const withTracker = (WrappedComponent: Class<React.Component<*, *>>) => {
  const debug = SETTINGS.reactGaDebug === "true"

  if (SETTINGS.gaTrackingID) {
    ReactGA.initialize(SETTINGS.gaTrackingID, { debug: debug })
  }

  const HOC = (props: Object) => {
    return <WrappedComponent {...props} />
  }

  return HOC
}

export default withTracker
