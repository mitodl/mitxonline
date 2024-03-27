// @flow
import React from "react"

import { Formik, Field, Form } from "formik"

import { PasswordInput, EmailInput } from "./elements/inputs"
import CardLabel from "../input/CardLabel"

import type { User } from "../../flow/authTypes"

import { changeEmailValidationRegex } from "../../lib/validation"

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
      initialValues={{
        email:           user.email,
        confirmPassword: ""
      }}
      render={({ isSubmitting }) => (
        <Form>
          <section className="email-section">
            <h2 aria-label="Form Change Email">Change Email</h2>
            <div className="form-group">
              <CardLabel htmlFor="email" isRequired={true} label="Email" />
              <Field
                name="email"
                id="email"
                className="form-control"
                component={EmailInput}
                autoComplete="email"
                required
                pattern={changeEmailValidationRegex(user.email)}
                title="Email must be different than your current one."
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
                aria-describedby="confirmPasswordError"
                aria-label="Confirm Password"
                required
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
      )}
    />
  )
}

export default ChangeEmailForm
