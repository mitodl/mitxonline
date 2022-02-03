import { ErrorMessage, Field, Form, Formik } from "formik"
import React from "react"
import { changePasswordFormValidation } from "../../lib/validation"
import FormError from "./elements/FormError"
import { PasswordInput } from "./elements/inputs"

type Props = {
  onSubmit: (...args: Array<any>) => any
}
export type ChangePasswordFormValues = {
  oldPassword: string
  newPassword: string
  confirmPassword: string
}

const ChangePasswordForm = ({ onSubmit }: Props) => (
  <Formik
    onSubmit={onSubmit}
    validationSchema={changePasswordFormValidation}
    initialValues={{
      oldPassword:     "",
      newPassword:     "",
      confirmPassword: ""
    }}
    render={({ isSubmitting }) => (
      <Form>
        <section className="email-section">
          <h4>Change Password</h4>
          <div className="form-group">
            <label htmlFor="oldPassword">
              Old Password<span className="required">*</span>
            </label>
            <Field
              name="oldPassword"
              id="oldPassword"
              className="form-control"
              component={PasswordInput}
              aria-describedby="oldPasswordError"
            />
            <ErrorMessage
              name="oldPassword"
              id="oldPasswordError"
              component={FormError}
            />
          </div>
          <div className="form-group">
            <label htmlFor="newPassword">
              New Password<span className="required">*</span>
            </label>
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
            <label htmlFor="confirmPassword">
              Confirm Password<span className="required">*</span>
            </label>
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
        </section>
        <div className="row submit-row no-gutters justify-content-end">
          <button
            type="submit"
            className="btn btn-primary"
            disabled={isSubmitting}
          >
            Submit
          </button>
        </div>
      </Form>
    )}
  />
)

export default ChangePasswordForm
