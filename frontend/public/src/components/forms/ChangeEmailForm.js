// @flow
import React from "react"

import { Formik, Field, Form, ErrorMessage } from "formik"

import { PasswordInput, EmailInput } from "./elements/inputs"
import CardLabel from "../input/CardLabel"

import type { User } from "../../flow/authTypes"

import {
  changeEmailFormValidation,
  changeEmailValidationRegex
} from "../../lib/validation"
import FormError from "./elements/FormError"
import { ConnectedFocusError } from "focus-formik-error"

type Props = {
  onSubmit: Function,
  user: User
}

export type ChangeEmailFormValues = {
  email: string,
  confirmPassword: string
}

const ChangeEmailForm = ({ onSubmit, user }: Props) => {
  return (
    <Formik
      onSubmit={onSubmit}
      validationSchema={changeEmailFormValidation}
      initialValues={{
        email:           user.email,
        confirmPassword: ""
      }}
    >
      {({ isSubmitting, errors }) => {
        return (
          <Form>
            <ConnectedFocusError />
            <section className="email-section">
              <h2 aria-label="Change Email Form">Change Email</h2>
              <div className="form-group">
                <CardLabel htmlFor="email" isRequired={true} label="Email" />
                <Field
                  name="email"
                  id="email"
                  className="form-control"
                  component={EmailInput}
                  autoComplete="email"
                  pattern={changeEmailValidationRegex(user.email)}
                  title="Email must be different than your current one."
                  aria-invalid={errors.email ? "true" : null}
                  aria-describedby={errors.email ? "emailError" : null}
                />
                <ErrorMessage
                  name="email"
                  id="emailError"
                  component={FormError}
                />
              </div>
              <div className="form-group">
                <CardLabel
                  htmlFor="confirmPassword"
                  isRequired={true}
                  label="Confirm Password"
                  subLabel="Password required to change email address"
                />
                <Field
                  id="confirmPassword"
                  name="confirmPassword"
                  className="form-control"
                  component={PasswordInput}
                  autoComplete="current-password"
                  aria-invalid={errors.confirmPassword ? "true" : null}
                  aria-describedby={
                    errors.confirmPassword ? "confirmPasswordError" : null
                  }
                  aria-label="Confirm Password"
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
                  aria-label="sumbit form change email"
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
}

export default ChangeEmailForm
