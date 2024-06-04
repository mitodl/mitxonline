// @flow
import React from "react"

import { Formik, Field, Form, ErrorMessage } from "formik"

import { EmailInput } from "./elements/inputs"
import FormError from "./elements/FormError"
import * as yup from "yup"
import { ConnectedFocusError } from "focus-formik-error"
import CardLabel from "../input/CardLabel"
import { emailField } from "../../lib/validation"

type EmailFormProps = {
  onSubmit: Function,
  children?: React$Element<*>
}

export type EmailFormValues = {
  email: string
}

const EmailFormValidation = yup.object().shape({
  email: emailField
})

const EmailForm = ({ onSubmit, children }: EmailFormProps) => (
  <Formik
    onSubmit={onSubmit}
    initialValues={{ email: "" }}
    validationSchema={EmailFormValidation}
    validateOnChange={false}
    validateOnBlur={false}
  >
    {({ isSubmitting, errors }) => {
      return (
        <Form noValidate>
          <ConnectedFocusError />
          <div className="form-group small-gap">
            <CardLabel htmlFor="email" isRequired={true} label="Email" />
            <Field
              name="email"
              id="email"
              className="form-control"
              component={EmailInput}
              autoComplete="email"
              aria-invalid={errors.email ? "true" : null}
              aria-describedby={errors.email ? "emailError" : null}
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
      )
    }}
  </Formik>
)

export default EmailForm
