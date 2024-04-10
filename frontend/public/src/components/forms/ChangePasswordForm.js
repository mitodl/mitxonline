// @flow
import React from "react"

import { Formik, Field, Form, ErrorMessage } from "formik"

import { PasswordInput } from "./elements/inputs"
import FormError from "./elements/FormError"
import {
  passwordFieldRegex,
  passwordFieldErrorMessage,
  changePasswordFormValidation
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
        <Form>
          <ConnectedFocusError />
          <section className="email-section">
            <h2 aria-label="Change Password Form">Change Password</h2>
            <div className="form-group">
              <CardLabel
                htmlFor="oldPassword"
                isRequired={true}
                label="Old Password"
              />
              <Field
                name="oldPassword"
                id="oldPassword"
                className="form-control"
                component={PasswordInput}
                autoComplete="current-password"
                aria-label="Old Password"
                aria-invalid={errors.oldPassword ? "true" : null}
                aria-describedby={
                  errors.oldPassword ? "odlPasswordError" : null
                }
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
                aria-label="New Password"
                aria-invalid={errors.newPassword ? "true" : null}
                aria-describedby={
                  errors.newPassword ? "newPasswordError" : null
                }
                pattern={passwordFieldRegex}
                title={passwordFieldErrorMessage}
              />
              <ErrorMessage
                name="newPassword"
                id="newPasswordError"
                component={FormError}
              />
            </div>
            <div className="form-group">
              <CardLabel
                htmlFor="confirmPassword"
                isRequired={true}
                label="Confirm Password"
              />
              <Field
                name="confirmPassword"
                id="confirmPassword"
                className="form-control"
                component={PasswordInput}
                autoComplete="new-password"
                aria-label="Confirm Password"
                aria-invalid={errors.confirmPassword ? "true" : null}
                aria-describedby={
                  errors.confirmPassword ? "confirmPasswordError" : null
                }
                pattern={passwordFieldRegex}
                title={passwordFieldErrorMessage}
              />
              <ErrorMessage
                name="confirmPassword"
                id="confirmPasswordError"
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
