import React from "react"

declare module "formik" {
  export interface ErrorMessageProps {
    id?: string
  }
}

// NOTE: formik is weird here, we can't strongly type props or type checking will fail everywhere we use this
// @ts-ignore
export default function FormError(props) {
  const { children, ...rest } = props
  return (
    <div className="form-error" role="alert" {...rest}>
      {children}
    </div>
  )
}
