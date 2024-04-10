// @flow
import React from "react"
import * as yup from "yup"

import { Formik, Field, Form, ErrorMessage } from "formik"
import { Link } from "react-router-dom"

import { PasswordInput } from "./elements/inputs"
import { routes } from "../../lib/urls"
import FormError from "./elements/FormError"
import { ConnectedFocusError } from "focus-formik-error"

type LoginPasswordFormProps = {
  onSubmit: Function
}
const passwordValidation = yup.object().shape({
  password: yup.string().required("Password is required")
})

const LoginPasswordForm = ({ onSubmit }: LoginPasswordFormProps) => (
  <Formik
    onSubmit={onSubmit}
    initialValues={{ password: "" }}
    validationSchema={passwordValidation}
    validateOnChange={false}
    validateOnBlur={false}
  >
    {({ isSubmitting, errors }) => {
      return (
        <Form>
          <ConnectedFocusError />
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <Field
              name="password"
              id="password"
              className="form-control"
              component={PasswordInput}
              autoComplete="current-password"
              aria-invalid={errors.password ? "true" : null}
              aria-describedby={errors.password ? "passwordError" : null}
            />
            <ErrorMessage
              name="password"
              id="passwordError"
              component={FormError}
            />
          </div>
          <div className="form-group">
            <Link to={routes.login.forgot.begin}>Forgot Password?Here</Link>
          </div>
          <div className="row submit-row no-gutters">
            <div className="col d-flex justify-content-end">
              <button
                type="submit"
                className="btn btn-primary btn-gradient-red-to-blue large"
                disabled={isSubmitting}
              >
                Sign in
              </button>
            </div>
          </div>
        </Form>
      )
    }}
  </Formik>
)

export default LoginPasswordForm
