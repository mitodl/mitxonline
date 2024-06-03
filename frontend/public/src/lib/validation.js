// @flow
import * as yup from "yup"

// Field validations

export const passwordFieldRegex = /^(?=.*[0-9])(?=.*[a-zA-Z]).{8,}$/

const newAndConfirmPasswordMatchErrorMessage =
  "New password and Confirm Password must match." // pragma: allowlist secret

export const passwordFieldErrorMessage =
  "Password must be atleast 8 characters and contain at least one letter and number."

export const usernameFieldErrorMessage =
  "Username must be between 3 and 30 characters."

const validEmailRegex = /^(([^<>()[\]\\.,;:\s@"]+(\.[^<>()[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/

const validEmailErrorMessage = "Please enter a valid email address."

export const passwordField = yup
  .string()
  .required()
  .label("Password")

export const changeEmailFormValidation = currentEmail =>
  yup.object().shape({
    email: yup
      .string()
      .label("New Email")
      .required()
      .matches(validEmailRegex, validEmailErrorMessage)
      .test(
        "emails must be different",
        "New email must be different from current email.",
        function(newEmail) {
          if (currentEmail === newEmail) return false
          return true
        }
      ),
    confirmPasswordEmailChange: passwordField.label("Confirm Password")
  })

export const newPasswordField = passwordField
  .label("New Password")
  .matches(passwordFieldRegex, passwordFieldErrorMessage)

export const usernameField = yup
  .string()
  .required()
  .label("Username")
  .min(3, usernameFieldErrorMessage)
  .max(30, usernameFieldErrorMessage)

export const resetPasswordFormValidation = yup.object().shape({
  newPassword: newPasswordField
    .label("New Password")
    .oneOf(
      [yup.ref("confirmPassword")],
      newAndConfirmPasswordMatchErrorMessage
    ),
  confirmPassword: newPasswordField
    .label("Confirm Password")
    .oneOf([yup.ref("newPassword")], newAndConfirmPasswordMatchErrorMessage)
})

export const changePasswordFormValidation = yup.object().shape({
  oldPassword: passwordField.label("Old Password"),

  newPassword: newPasswordField.oneOf(
    [yup.ref("confirmPassword")],
    newAndConfirmPasswordMatchErrorMessage
  ),

  confirmPassword: newPasswordField
    .label("Confirm Password")
    .oneOf([yup.ref("newPassword")], newAndConfirmPasswordMatchErrorMessage)
})
