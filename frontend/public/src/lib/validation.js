// @flow
import * as yup from "yup"

// Field validations

export const passwordFieldRegex = "^(?=.*[0-9])(?=.*[a-zA-Z]).{8,}$"

export const passwordFieldErrorMessage =
  "Password must be atleast 8 character and contain at least one letter and number."

export const usernameFieldRegex = "^\\S{3,30}$"

export const usernameFieldErrorMessage =
  "Username must be between 3 and 30 characters."

export const changeEmailValidationRegex = (email: string) => {
  const escapedUserEmail = email.replace(
    /[-[\]{}()*+!<=:?./\\^$|#\s,]/g,
    "\\$&"
  )
  return `^((?!${escapedUserEmail}).)*$`
}

export const changeEmailFormValidation = yup.object().shape({
  email: yup
    .string()
    .label("New Email")
    .required(),
  confirmPassword: yup
    .string()
    .label("Confirm Password")
    .required()
})

export const passwordField = yup
  .string()
  .required()
  .label("Password")

export const usernameField = yup
  .string()
  .required()
  .label("Username")

export const resetPasswordFormValidation = yup.object().shape({
  newPassword:     passwordField.label("New Password"),
  confirmPassword: yup
    .string()
    .label("Confirm Password")
    .required()
    .oneOf([yup.ref("newPassword")], "Passwords must match")
})

export const changePasswordFormValidation = yup.object().shape({
  oldPassword: yup
    .string()
    .label("Old Password")
    .required(),

  newPassword: passwordField.label("New Password").required(),

  confirmPassword: yup
    .string()
    .label("Confirm Password")
    .required()
    .oneOf([yup.ref("newPassword")], "Passwords must match")
})
