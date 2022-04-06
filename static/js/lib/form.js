// @flow
import React from "react"

export const formatErrors = (
  errors: string | Object | null
): React$Element<*> | null => {
  if (!errors) {
    return null
  }

  let errorString
  if (typeof errors === "object") {
    errorString = Object.values(errors).filter(error => error)[0]
  } else {
    errorString = errors
  }
  // $FlowFixMe
  return <div className="error">{errorString}</div>
}

export const formatSuccessMessage = (message: string): React$Element<*> => {
  return <div className="success">{message}</div>
}
