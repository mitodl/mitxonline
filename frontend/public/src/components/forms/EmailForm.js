// @flow
import React from "react"

import { Formik, Field, Form, ErrorMessage } from "formik"

import { EmailInput } from "./elements/inputs"
import FormError from "./elements/FormError"
import * as yup from "yup"

type EmailFormProps = {
  onSubmit: Function,
  children?: React$Element<*>
}

export type EmailFormValues = {
  email: string
}

const EmailFormValidation = yup.object().shape({
  email: yup
    .string()
    .email("Please enter an email address")
    .required("Email is required")
})

const EmailForm = ({ onSubmit, children }: EmailFormProps) => (
  <Formik
    onSubmit={onSubmit}
    initialValues={{ email: "" }}
    validationSchema={EmailFormValidation}
    validateOnChange={false}
    validateOnBlur={false}
    render={({ isSubmitting }) => (
      <Form>
        <div className="form-group small-gap">
          <label htmlFor="email">Email</label>
          <Field
            name="email"
            id="email"
            className="form-control"
            component={EmailInput}
            autoComplete="email"
            aria-errormessage="emailError"
            required
          />
          <ErrorMessage name="email" id="emailError" component={FormError} />
        </div>
        {children}
        <div className="form-group">
          <button
            type="submit"
            className="btn btn-primary btn-gradient-red-to-blue large"
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
