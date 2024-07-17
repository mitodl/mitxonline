// @flow
import React from "react"

import { Formik, Field, Form, ErrorMessage } from "formik"

import { PasswordInput } from "./elements/inputs"
import FormError from "./elements/FormError"
import {
  resetPasswordFormValidation,
  passwordFieldErrorMessage
} from "../../lib/validation"
import CardLabel from "../input/CardLabel"
import { ConnectedFocusError } from "focus-formik-error"

type Props = {
  onSubmit: Function
}

export type ResetPasswordFormValues = {
  newPassword: string,
  confirmPasswordChangePassword: string
}

const ResetPasswordForm = ({ onSubmit }: Props) => (
  <Formik
    onSubmit={onSubmit}
    validationSchema={resetPasswordFormValidation}
    initialValues={{
      newPassword:   "",
      reNewPassword: ""
    }}
    validateOnChange={false}
    validateOnBlur={false}
  >
    {({ isSubmitting, errors }) => {
      return (
        <Form noValidate>
          <ConnectedFocusError />
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
              aria-invalid={errors.newPassword ? "true" : null}
              aria-describedby={errors.newPassword ? "newPasswordError" : null}
              title={passwordFieldErrorMessage}
              autoComplete="new-password"
              required
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
              label="Confirm New Password"
            />
            <Field
              name="confirmPasswordChangePassword"
              id="confirmPasswordChangePassword"
              className="form-control"
              component={PasswordInput}
              aria-invalid={
                errors.confirmPasswordChangePassword ? "true" : null
              }
              aria-describedby={
                errors.confirmPasswordChangePassword ?
                  "confirmPasswordChangePasswordError" :
                  null
              }
              autoComplete="new-password"
              required
              title={passwordFieldErrorMessage}
            />
            <ErrorMessage
              name="confirmPasswordChangePassword"
              id="confirmPasswordChangePasswordError"
              component={FormError}
            />
          </div>
          <div className="row submit-row no-gutters">
            <div className="col d-flex justify-content-end">
              <button
                type="submit"
                className="btn btn-primary btn-gradient-red-to-blue large"
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

export default ResetPasswordForm
