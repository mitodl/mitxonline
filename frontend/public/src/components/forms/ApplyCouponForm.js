// @flow
import React from "react"
import { Formik, Form, ErrorMessage, Field } from "formik"

type Props = {
  onSubmit: Function,
  couponCode: string,
  discounts: Array<Object>,
  discountCodeIsBad: boolean
}

const getInitialValues = (couponCode, discounts, discountCodeIsBad) => ({
  couponCode:        couponCode,
  discounts:         discounts,
  discountCodeIsBad: discountCodeIsBad
})

const ApplyCouponForm = ({
  onSubmit,
  couponCode,
  discounts,
  discountCodeIsBad
}: Props) => (
  <Formik
    onSubmit={onSubmit}
    initialValues={getInitialValues(couponCode, discounts, discountCodeIsBad)}
    render={({ isSubmitting, setFieldValue, setFieldTouched, values }) => (
      <Form>
        <div className="row">
          <div className="col-12 mt-4 px-3 py-3 py-md-0">
            <label htmlFor="couponCode">
              <span id="couponCodeDesc">Have a coupon?</span>
            </label>
            {discountCodeIsBad ? (
              <div
                id="invalidCode"
                className="text-primary mt-2 font-weight-bold cart-text-smaller"
              >
                Discount code is invalid.
              </div>
            ) : null}
            <div className="d-flex justify-content-between flex-sm-column flex-md-row">
              <Field
                type="text"
                name="couponCode"
                id="couponCode"
                className="form-control"
                autoComplete="given-name"
                aria-describedby="couponCodeDesc"
              />

              <button
                className="btn btn-primary btn-red btn-halfsize mx-2 highlight font-weight-normal"
                type="submit"
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
        </div>
      </Form>
    )}
  />
)

export default ApplyCouponForm
