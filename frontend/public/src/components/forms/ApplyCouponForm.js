import React from "react"
import { Form, ErrorMessage, Field } from "formik"
import FormError from "./elements/FormError"
import { ConnectedFocusError } from "focus-formik-error"

type Props = {
  discounts: Array<Object>
}

const ApplyCouponForm = ({ discounts }: Props) => (
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
            autoComplete="off"
            aria-describedby="couponCodeError"
          />
          <ErrorMessage
            name="couponCode"
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
      {discounts && discounts.length > 0 && (
        <div
          id="codeApplicationWarning"
          className="text-primary mt-2 font-weight-bold cart-text-smaller"
        >
          Adding another coupon will replace the currently applied coupon.
        </div>
      )}
    </div>
  </Form>
)

export default ApplyCouponForm