// @flow
import React from "react"
import { assert, expect } from "chai"
import { shallow, mount } from "enzyme"

import ApplyCouponForm from "./ApplyCouponForm"
import { Formik } from "formik"

describe("ApplyCouponForm", () => {
  const discounts = []

  const renderForm = (props = {}) =>
    shallow(
      <Formik initialValues={{ couponCode: "" }} onSubmit={() => {}}>
        <ApplyCouponForm discounts={discounts} {...props} />
      </Formik>
    )
      .dive()
      .dive()

  it("renders the error if couponCode has an error", () => {
    const wrapper = mount(
      <Formik
        initialValues={{ couponCode: "" }}
        initialErrors={{ couponCode: "Invalid code" }}
        initialTouched={{ couponCode: true }}
        onSubmit={() => {}}
      >
        <ApplyCouponForm discounts={[]} />
      </Formik>
    )

    expect(wrapper.find("div#couponCodeError").text()).to.equal("Invalid code")
  })

  it("does not render the overwrite warning text when there aren't discounts", () => {
    const wrapper = renderForm()
    assert.ok(!wrapper.find("div#codeApplicationWarning").exists())
  })

  it("renders the overwrite warning text if there's a discount applied already", () => {
    const wrapper = renderForm({ discounts: ["some-discount"] })
    assert.ok(wrapper.find("div#codeApplicationWarning").exists())
  })
})
