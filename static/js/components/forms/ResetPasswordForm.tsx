import { ErrorMessage, Field, Form, Formik } from "formik"
import React from "react"
import { resetPasswordFormValidation } from "../../lib/validation"
import FormError from "./elements/FormError"
import { PasswordInput } from "./elements/inputs"

type Props = {
  onSubmit: (...args: Array<any>) => any
}
export type ResetPasswordFormValues = {
  newPassword: string
  confirmPassword: string
}

const ResetPasswordForm = ({ onSubmit }: Props) => (
  <Formik
    onSubmit={onSubmit}
    validationSchema={resetPasswordFormValidation}
    initialValues={{
      newPassword:   "",
      reNewPassword: ""
    }}
    render={({ isSubmitting }) => (
      <Form>
        <div className="form-group">
          <label htmlFor="newPassword">New Password</label>
          <Field
            name="newPassword"
            id="newPassword"
            className="form-control"
            component={PasswordInput}
            aria-describedby="newPasswordError"
          />
          <ErrorMessage
            name="newPassword"
            id="newPasswordError"
            component={FormError}
          />
        </div>
        <div className="form-group">
          <label htmlFor="confirmPassword">Confirm Password</label>
          <Field
            name="confirmPassword"
            id="confirmPassword"
            className="form-control"
            component={PasswordInput}
            aria-describedby="confirmPasswordError"
          />
          <ErrorMessage
            name="confirmPassword"
            id="confirmPasswordError"
            component={FormError}
          />
        </div>
        <div className="row submit-row no-gutters justify-content-end">
          <button
            type="submit"
            className="btn btn-primary btn-gradient-red large"
            disabled={isSubmitting}
          >
            Submit
          </button>
        </div>
      </Form>
    )}
  />
)

export default ResetPasswordForm
