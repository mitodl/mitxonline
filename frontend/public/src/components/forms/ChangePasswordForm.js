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
          <h2>Change Password</h2>
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
              required
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
              aria-describedby="newPasswordError"
              aria-label="New Password"
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
              aria-describedby="confirmPasswordError"
              aria-label="Confirm Password"
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
