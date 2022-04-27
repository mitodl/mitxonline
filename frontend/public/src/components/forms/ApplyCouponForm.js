// @flow
import React from "react"
import { Formik, Form, ErrorMessage, Field } from "formik"
import FormError from "./elements/FormError"

type Props = {
  onSubmit: Function,
  couponCode: string,
  discounts: Array<Object>,
}

const getInitialValues = (couponCode, discounts) => ({
  couponCode:        couponCode,
  discounts:         discounts,
})

const ApplyCouponForm = ({
  onSubmit,
  couponCode,
  discounts,
}: Props) => (
  <Formik
    onSubmit={onSubmit}
    initialValues={getInitialValues(couponCode, discounts)}
    render={({ isSubmitting, setFieldValue, setFieldTouched, values }) => (
      <Form>
        <div className="row">
          <div className="col-12 mt-4 px-3 py-3 py-md-0">
            <label htmlFor="couponCode">
              <span>Have a coupon?</span>
            </label>
            <div className="d-flex justify-content-between flex-sm-column flex-md-row">
              <div className="pt-2">
                <Field
                  type="text"
                  name="couponCode"
                  id="couponCode"
                  className="form-control"
                  autoComplete="given-name"
                  aria-describedby="couponCodeError"
                />
                <ErrorMessage name="couponCode" className="form-control" id="couponCodeError" component={FormError} />
              </div>

              <div>
                <button
                  className="btn btn-primary btn-red btn-halfsize mx-2 highlight font-weight-normal"
                  type="submit"
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
