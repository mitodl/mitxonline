// @flow
import React from "react"

import { Formik, Field, Form, ErrorMessage } from "formik"

import { PasswordInput } from "./elements/inputs"
import FormError from "./elements/FormError"
import {
  changePasswordFormValidation,
  passwordFieldErrorMessage
} from "../../lib/validation"
import CardLabel from "../input/CardLabel"
import { ConnectedFocusError } from "focus-formik-error"

type Props = {
  onSubmit: Function
}

export type ChangePasswordFormValues = {
  oldPassword: string,
  newPassword: string,
  confirmPassword: string
}

const ChangePasswordForm = ({ onSubmit }: Props) => (
  <Formik
    onSubmit={onSubmit}
    validationSchema={changePasswordFormValidation}
    initialValues={{
      oldPassword:     "",
      newPassword:     "",
      confirmPassword: ""
    }}
    validateOnChange={false}
    validateOnBlur={false}
  >
    {({ isSubmitting, errors }) => {
      return (
        <Form noValidate>
          <ConnectedFocusError />
          <section className="email-section">
            <h2 aria-label="Change Password Form">Change Password</h2>
            <div className="form-group">
              <CardLabel
                htmlFor="currentPassword"
                isRequired={true}
                label="Current Password"
              />
              <Field
                name="currentPassword"
                id="currentPassword"
                className="form-control"
                component={PasswordInput}
                autoComplete="current-password"
                required
                aria-invalid={errors.currentPassword ? "true" : null}
                aria-describedby={
                  errors.currentPassword ? "currentPasswordError" : null
                }
              />
              <ErrorMessage
                name="currentPassword"
                id="currentPasswordError"
                component={FormError}
              />
            </div>
            <div className="form-group">
              <CardLabel
                htmlFor="newPassword"
                isRequired={true}
                label="New Password"
              />
              <Field
                name="newPassword"
                id="newPassword"
                className="form-control"
                component={PasswordInput}
                autoComplete="new-password"
                required
                aria-invalid={errors.newPassword ? "true" : null}
                aria-describedby={
                  errors.newPassword ? "newPasswordError" : null
                }
                aria-description={passwordFieldErrorMessage}
              />
              <ErrorMessage
                name="newPassword"
                id="newPasswordError"
                component={FormError}
              />
            </div>
            <div className="form-group">
              <CardLabel
                htmlFor="confirmPasswordChangePassword"
                isRequired={true}
                label="Confirm Password"
              />
              <Field
                name="confirmPasswordChangePassword"
                id="confirmPasswordChangePassword"
                className="form-control"
                component={PasswordInput}
                autoComplete="new-password"
                required
                aria-invalid={
                  errors.confirmPasswordChangePassword ? "true" : null
                }
                aria-describedby={
                  errors.confirmPasswordChangePassword
                    ? "confirmPasswordChangePasswordError"
                    : null
                }
                aria-description={passwordFieldErrorMessage}
              />
              <ErrorMessage
                name="confirmPasswordChangePassword"
                id="confirmPasswordChangePasswordError"
                component={FormError}
              />
            </div>
          </section>
          <div className="row submit-row no-gutters">
            <div className="col d-flex justify-content-end">
              <button
                type="submit"
                aria-label="submit form change password"
                className="btn btn-primary btn-gradient-red-to-blue"
                disabled={isSubmitting}
              >
                Submit
              </button>
            </div>
          </div>
        </Form>
      )
    }}
  </Formik>
)

export default ChangePasswordForm
