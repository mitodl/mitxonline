// @flow
import * as yup from "yup"

// Field validations

export const passwordFieldRegex = /^(?=.*[0-9])(?=.*[a-zA-Z]).{8,}$/

const newAndConfirmPasswordMatchErrorMessage = "New password and Confirm Password must match."

export const passwordFieldErrorMessage =
  "Password must be atleast 8 characters and contain at least one letter and number."

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

export const newPasswordField = passwordField
  .label("New Password")
  .matches(
    passwordFieldRegex,
    passwordFieldErrorMessage
  )

export const usernameField = yup
  .string()
  .required()
  .label("Username")

export const resetPasswordFormValidation = yup.object().shape({
  newPassword:     newPasswordField.label("New Password")
    .oneOf([yup.ref("confirmPassword")], newAndConfirmPasswordMatchErrorMessage),
  confirmPassword: newPasswordField
    .label("Confirm Password")
    .oneOf([yup.ref("newPassword")], newAndConfirmPasswordMatchErrorMessage)
})

export const changePasswordFormValidation = yup.object().shape({
  oldPassword: passwordField.label("Old Password"),

  newPassword: newPasswordField.oneOf([yup.ref("confirmPassword")], newAndConfirmPasswordMatchErrorMessage),

  confirmPassword: newPasswordField.label("Confirm Password")
    .oneOf([yup.ref("newPassword")], newAndConfirmPasswordMatchErrorMessage)
})
