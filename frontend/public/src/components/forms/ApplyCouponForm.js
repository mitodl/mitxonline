// @flow
import React from "react"
import { Formik, Form, ErrorMessage, Field } from "formik"
import FormError from "./elements/FormError"

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
    render={() => (
      <Form>
        <div className="row g-0 coupon-form">
          <div className="col-12">
            <label htmlFor="couponCode" className="fw-bold">
              Coupon code
            </label>
            <div className="d-flex justify-content-between flex-sm-column flex-md-row">
              <div className="col-sm-6 col-md-8">
                <Field
                  type="text"
                  name="couponCode"
                  id="couponCode"
                  className="form-control"
                  autoComplete="given-name"
                  aria-describedby="couponCodeError"
                />
                <ErrorMessage
                  name="couponCode"
                  className="form-control"
                  id="couponCodeError"
                  component={FormError}
                />
              </div>

              <div className="col-6 col-md-4">
                <button
                  className="btn btn-primary btn-red btn-halfsize mx-2 highlight font-weight-normal w-100"
                  type="submit"
                  aria-label="Apply coupon"
                >
                  Apply
                </button>
              </div>
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
        </div>
      </Form>
    )}
  />
)

export default ApplyCouponForm
