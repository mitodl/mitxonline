// @flow
import React from "react"
import { Formik, Form, ErrorMessage, Field } from "formik"
import FormError from "./elements/FormError"
import { ConnectedFocusError } from "focus-formik-error"

type Props = {
  onSubmit: Function,
  couponCode: string,
  discounts: Array<Object>
}

const getInitialValues = (couponCode, discounts) => ({
  couponCode: couponCode,
  discounts:  discounts
})

const ApplyCouponForm = ({ onSubmit, couponCode, discounts }: Props) => (
  <Formik
    onSubmit={onSubmit}
    initialValues={getInitialValues(couponCode, discounts)}
  >
    {({ errors }) => {
      return (
        <Form>
          <ConnectedFocusError />
          <div className="coupon-form">
            <div className="d-flex align-content-end align-items-end justify-content-between flex-sm-column flex-md-row">
              <div className="form-group">
                <label htmlFor="couponCode" className="fw-bold">
                  Coupon code
                </label>
                <Field
                  type="text"
                  name="couponCode"
                  id="couponCode"
                  className="form-control"
                  autoComplete="given-name"
                  aria-invalid={errors.couponCode ? "true" : null}
                  aria-describedby={
                    errors.couponCode ? "couponCodeError" : null
                  }
                />
                <ErrorMessage
                  name="couponCode"
                  className="form-control"
                  id="couponCodeError"
                  component={FormError}
                />
              </div>

              <button
                className="btn btn-primary btn-gradient-red-to-blue btn-apply-coupon"
                type="submit"
                aria-label="Apply coupon"
              >
                Apply
              </button>
            </div>
            {discounts !== null && discounts.length > 0 ? (
              <div
                id="codeApplicationWarning"
                className="text-primary mt-2 font-weight-bold cart-text-smaller"
              >
                Adding another coupon will replace the currently applied coupon.
              </div>
            ) : null}
          </div>
        </Form>
      )
    }}
  </Formik>
)

export default ApplyCouponForm
