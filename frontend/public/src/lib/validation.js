// @flow
import * as yup from "yup"

import { USERNAME_LENGTH } from "../constants"

// Field validations

export const emailFieldValidation = yup
  .string()
  .label("Email")
  .required()
  .email("Invalid email")

export const passwordFieldValidation = yup
  .string()
  .label("Password")
  .required()
  .min(8)

export const usernameFieldValidation = yup
  .string()
  .label("Username")
  .trim()
  .required()
  .min(3)
  .max(USERNAME_LENGTH)

export const newPasswordFieldValidation = passwordFieldValidation.matches(
  /^(?=.*[0-9])(?=.*[a-zA-Z]).*$/,
  {
    message: "Password must contain at least one letter and number"
  }
)

export const resetPasswordFormValidation = yup.object().shape({
  newPassword:     newPasswordFieldValidation.label("New Password"),
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

  newPassword: newPasswordFieldValidation.label("New Password"),

  confirmPassword: yup
    .string()
    .label("Confirm Password")
    .required()
    .oneOf([yup.ref("newPassword")], "Passwords must match")
})

export const changeEmailFormValidation = yup.object().shape({
  email: emailFieldValidation.notOneOf(
    [yup.ref("$currentEmail")],
    "Email cannot be the same. Please use a different one."
  ),

  confirmPassword: passwordFieldValidation.label("Confirm Password")
})
