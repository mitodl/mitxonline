// @flow
import React from "react"
import sinon from "sinon"
import { assert } from "chai"
import { shallow } from "enzyme"

import ApplyCouponForm from "./ApplyCouponForm"

import { findFormikFieldByName } from "../../lib/test_utils"

describe("ApplyCouponForm", () => {
  let sandbox, onSubmitStub, couponCode
  const discounts = []

  const renderForm = (props = {}) =>
    shallow(
      <Formik initialValues={{ couponCode: "" }} onSubmit={() => {}}>
        <ApplyCouponForm discounts={discounts} {...props} />
      </Formik>
    )
      .dive()
      .dive()

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    onSubmitStub = sandbox.stub()
  })

  it("does not render the error", () => {
    const wrapper = renderForm()
    const form = wrapper.find("Formik").dive()
    assert.ok(!form.find("div#couponCodeError").exists())
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
