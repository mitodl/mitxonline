// @flow
import React from "react"
import * as yup from "yup"

import { Formik, Field, Form, ErrorMessage } from "formik"
import { Link } from "react-router-dom"

import FormError from "./elements/FormError"
import { PasswordInput } from "./elements/inputs"
import { passwordFieldValidation } from "../../lib/validation"
import { routes } from "../../lib/urls"

const passwordValidation = yup.object().shape({
  password: passwordFieldValidation
})

type LoginPasswordFormProps = {
  onSubmit: Function
}

const LoginPasswordForm = ({ onSubmit }: LoginPasswordFormProps) => (
  <Formik
    onSubmit={onSubmit}
    validationSchema={passwordValidation}
    initialValues={{ password: "" }}
    validateOnChange={false}
    validateOnBlur={false}
    render={({ isSubmitting }) => (
      <Form>
        <div className="form-group">
          <label htmlFor="password">Password</label>
          <Field
            name="password"
            id="password"
            className="form-control"
            component={PasswordInput}
            autoComplete="current-password"
            aria-describedby="passwordError"
            required
          />
          <ErrorMessage
            name="password"
            id="passwordError"
            component={FormError}
          />
        </div>
        <div className="form-group">
          <Link to={routes.login.forgot.begin} className="link-black">
            Forgot Password?
          </Link>
        </div>
        <div className="row submit-row no-gutters justify-content-end">
          <button
            type="submit"
            className="btn btn-primary btn-gradient-red large"
            disabled={isSubmitting}
          >
            Sign in
          </button>
        </div>
      </Form>
    )}
  />
)

export default LoginPasswordForm
