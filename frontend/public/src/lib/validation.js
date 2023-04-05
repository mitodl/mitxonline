// @flow
import * as yup from "yup"

// Field validations

export const passwordFieldRegex = "^(?=.*[0-9])(?=.*[a-zA-Z]).{8,}$"

export const passwordFieldErrorMessage =
  "Password must be atleast 8 character and contain at least one letter and number."

export const usernameFieldRegex = "^\\S{3,29}$"

export const usernameFieldErrorMessage =
  "Username must be between 3 and 29 characters."

export const passwordField = yup.string().label("Password")

export const usernameField = yup.string().label("Username")

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

  newPassword: passwordField.label("New Password"),

  confirmPassword: yup
    .string()
    .label("Confirm Password")
    .required()
    .oneOf([yup.ref("newPassword")], "Passwords must match")
})
