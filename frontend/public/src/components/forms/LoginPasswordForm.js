// @flow
import React from "react"

import { Formik, Field, Form } from "formik"
import { Link } from "react-router-dom"

import { PasswordInput } from "./elements/inputs"
import { routes } from "../../lib/urls"

type LoginPasswordFormProps = {
  onSubmit: Function
}

const LoginPasswordForm = ({ onSubmit }: LoginPasswordFormProps) => (
  <Formik
    onSubmit={onSubmit}
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
        </div>
        <div className="form-group">
          <Link to={routes.login.forgot.begin} className="link-black">
            Forgot Password?
          </Link>
        </div>
        <div className="row submit-row no-gutters">
          <div className="col d-flex justify-content-end">
            <button
              type="submit"
              className="btn btn-primary btn-gradient-red large"
              disabled={isSubmitting}
            >
              Sign in
            </button>
          </div>
        </div>
      </Form>
    )}
  />
)

export default LoginPasswordForm
