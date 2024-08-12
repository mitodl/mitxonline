// @flow
/* global SETTINGS: false */

// From https://github.com/ReactTraining/react-router/issues/4278#issuecomment-299692502
import React from "react"
import ga4 from "react-ga4"

const withTracker = (WrappedComponent: Class<React.Component<*, *>>) => {
  const debug = SETTINGS.reactGaDebug === "true"

  if (SETTINGS.gaTrackingID) {
    ga4.initialize(SETTINGS.gaTrackingID, { debug: debug })
  }

  const HOC = (props: Object) => {
    const page = props.location.pathname
    const title = props.location.title
    if (SETTINGS.gaTrackingID) {
      ga4.send({ hitType: "pageview", page: page, title: title })
    }
    return <WrappedComponent {...props} />
  }

  return HOC
}

export default withTracker
