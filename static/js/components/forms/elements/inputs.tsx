import { FieldProps } from "formik"
import React from "react"

const createTextInput = (inputType: string) => ({
  field,
  form,
  ...props
}: FieldProps & { [key: string]: any }) => {
  const { touched, errors } = form
  const errored = touched[field.name] && errors[field.name]
  const addedClasses = errored ? "errored" : ""
  return (
    <input
      type={inputType}
      {...field}
      {...props}
      className={`${props.className || ""} ${addedClasses}`}
    />
  )
}
export const TextInput = createTextInput("text")
export const EmailInput = createTextInput("email")
export const PasswordInput = createTextInput("password")
