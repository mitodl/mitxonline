// @flow
import React, { useEffect, useState } from "react"

import NotificationContainer from "./NotificationContainer"

// Delay any alert displayed on page-load by 500ms in order to
// ensure the alert is read by screen readers.
const DelayedNotificationContainer = () => {
  const [showComponent, setShowComponent] = useState(false)
  useEffect(() => {
    const timeout = setTimeout(() => {
      setShowComponent(true)
    }, 500)

    return () => clearTimeout(timeout)
  }, [])

  return showComponent ? <NotificationContainer /> : null
}

export default DelayedNotificationContainer
