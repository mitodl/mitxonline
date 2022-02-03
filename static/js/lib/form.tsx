import React from "react"

export const formatErrors = (
  errors: string | Record<string, any> | null
): React.ReactElement<React.ComponentProps<any>, any> | null => {
  if (!errors) {
    return null
  }

  let errorString

  if (typeof errors === "object") {
    errorString = Object.values(errors).filter(error => error)[0]
  } else {
    errorString = errors
  }
  return <div className="error">{errorString}</div>
}
export const formatSuccessMessage = (
  message: string
): React.ReactElement<React.ComponentProps<any>, any> => {
  return <div className="success">{message}</div>
}
