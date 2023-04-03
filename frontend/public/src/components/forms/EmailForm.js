// @flow
import React from "react"

import { Formik, Field, Form } from "formik"

import { EmailInput } from "./elements/inputs"


type EmailFormProps = {
  onSubmit: Function,
  children?: React$Element<*>
}

export type EmailFormValues = {
  email: string
}

const EmailForm = ({ onSubmit, children }: EmailFormProps) => (
  <Formik
    onSubmit={onSubmit}
    initialValues={{ email: "" }}
    validateOnChange={false}
    validateOnBlur={false}
    render={({ isSubmitting }) => (
      <Form>
        <div className="form-group">
          <label htmlFor="email">Email</label>
          <Field
            name="email"
            id="email"
            className="form-control"
            component={EmailInput}
            autoComplete="email"
            aria-describedby="emailError"
            required
          />
        </div>
        {children && <div className="form-group">{children}</div>}
        <div className="row submit-row no-gutters justify-content-end">
          <button
            type="submit"
            className="btn btn-primary btn-gradient-red large"
            disabled={isSubmitting}
          >
            Continue
          </button>
        </div>
      </Form>
    )}
  />
)

export default EmailForm
