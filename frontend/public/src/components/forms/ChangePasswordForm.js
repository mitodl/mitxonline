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
    render={({ isSubmitting }) => (
      <Form>
        <section className="email-section">
          <h1>Change Password</h1>
          <div className="form-group">
            <label htmlFor="oldPassword" className="fw-bold">
              Old Password<span className="required">*</span>
            </label>

            <Field
              name="oldPassword"
              id="oldPassword"
              className="form-control"
              component={PasswordInput}
              autoComplete="current-password"
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="newPassword" className="fw-bold">
              New Password<span className="required">*</span>
            </label>
            <Field
              name="newPassword"
              id="newPassword"
              className="form-control"
              component={PasswordInput}
              autoComplete="new-password"
              aria-describedby="newPasswordError"
              required
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
            <label htmlFor="confirmPassword" className="fw-bold">
              Confirm Password<span className="required">*</span>
            </label>
            <Field
              name="confirmPassword"
              id="confirmPassword"
              className="form-control"
              component={PasswordInput}
              autoComplete="new-password"
              aria-describedby="confirmPasswordError"
              required
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
              className="btn btn-primary btn-gradient-red-to-blue"
              disabled={isSubmitting}
            >
              Submit
            </button>
          </div>
        </div>
      </Form>
    )}
  />
)

export default ChangePasswordForm
