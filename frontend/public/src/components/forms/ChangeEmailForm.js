// @flow
import React from "react"

import { Formik, Field, Form, ErrorMessage } from "formik"

import { PasswordInput, EmailInput } from "./elements/inputs"
import CardLabel from "../input/CardLabel"

import type { User } from "../../flow/authTypes"

import {
  changeEmailFormValidation,
} from "../../lib/validation"
import FormError from "./elements/FormError"
import { ConnectedFocusError } from "focus-formik-error"

type Props = {
  onSubmit: Function,
  user: User
}

export type ChangeEmailFormValues = {
  email: string,
  confirmPasswordEmailChange: string
}

const ChangeEmailForm = ({ onSubmit, user }: Props) => (
  <Formik
    onSubmit={onSubmit}
    validationSchema={changeEmailFormValidation(user.email)}
    initialValues={{
      email:                      user.email,
      confirmPasswordEmailChange: ""
    }}
    validateOnChange={false}
    validateOnBlur={false}
  >
    {({ isSubmitting, errors }) => {
      return (
        <Form noValidate>
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
                aria-invalid={errors.email ? "true" : null}
                aria-describedby={errors.email ? "emailError" : null}
                required
              />
              <ErrorMessage
                name="email"
                id="emailError"
                component={FormError}
              />
            </div>
            <div className="form-group">
              <CardLabel
                htmlFor="confirmPasswordEmailChange"
                isRequired={true}
                label="Current Password"
                subLabel="Current password required to change email address"
              />
              <Field
                id="confirmPasswordEmailChange"
                name="confirmPasswordEmailChange"
                className="form-control"
                component={PasswordInput}
                autoComplete="current-password"
                aria-invalid={errors.confirmPasswordEmailChange ? "true" : null}
                aria-describedby={
                  errors.confirmPasswordEmailChange ? "confirmPasswordEmailChangeError" : null
                }
                required
              />
              <ErrorMessage
                name="confirmPasswordEmailChange"
                id="confirmPasswordEmailChangeError"
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

export default ChangeEmailForm
