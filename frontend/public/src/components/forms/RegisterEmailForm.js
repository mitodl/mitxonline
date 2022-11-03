// @flow
/* global SETTINGS:false */
import React from "react"
import * as yup from "yup"

import { Formik, Field, Form, ErrorMessage } from "formik"

import ScaledRecaptcha from "../ScaledRecaptcha"
import { EmailInput } from "./elements/inputs"
import FormError from "./elements/FormError"
import { emailFieldValidation } from "../../lib/validation"
import { routes } from "../../lib/urls"

const emailValidation = yup.object().shape({
  email:     emailFieldValidation,
  recaptcha: SETTINGS.recaptchaKey
    ? yup.string().required("Please verify you're not a robot")
    : yup.mixed().notRequired()
})

type Props = {
  onSubmit: Function
}

export type RegisterEmailFormValues = {
  email: string,
  recaptcha: ?string
}

const RegisterEmailForm = ({ onSubmit }: Props) => (
  <Formik
    onSubmit={onSubmit}
    validationSchema={emailValidation}
    initialValues={{
      email:     "",
      recaptcha: SETTINGS.recaptchaKey ? "" : undefined
    }}
    render={({ isSubmitting, setFieldValue }) => (
      <Form>
        <div className="form-group">
          <label htmlFor="email">Email</label>
          <Field
            name="email"
            id="email"
            className="form-control"
            autoComplete="email"
            component={EmailInput}
            aria-describedby="emailError"
          />
          <ErrorMessage name="email" id="emailError" component={FormError} />
          <p className="py-2">
            By creating an account I agree to the{" "}
            <a
              href={routes.informationLinks.honorCode}
              target="_blank"
              rel="noopener noreferrer"
            >
              Honor Code
            </a>
            {", "}
            <a
              href={routes.informationLinks.termsOfService}
              target="_blank"
              rel="noopener noreferrer"
            >
              Terms of Service
            </a>
            {" and "}
            <a
              href={routes.informationLinks.privacyPolicy}
              target="_blank"
              rel="noopener noreferrer"
            >
              Privacy Policy
            </a>
            {"."}
          </p>
        </div>
        {SETTINGS.recaptchaKey ? (
          <div className="form-group">
            <ScaledRecaptcha
              onRecaptcha={value => setFieldValue("recaptcha", value)}
              recaptchaKey={SETTINGS.recaptchaKey}
            />
            <ErrorMessage name="recaptcha" component={FormError} />
          </div>
        ) : null}
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

export default RegisterEmailForm
