// @flow
import React from "react"
import sinon from "sinon"
import { assert } from "chai"
import { shallow } from "enzyme"
import { Formik } from "formik"

import ApplyCouponForm from "./ApplyCouponForm"

import { findFormikFieldByName } from "../../lib/test_utils"

describe("ApplyCouponForm", () => {
  let sandbox, onSubmitStub, couponCode
  const discounts = []

  const renderForm = () =>
    shallow(
      <ApplyCouponForm
        onSubmit={onSubmitStub}
        couponCode={couponCode}
        discounts={discounts}
      />
    )

  beforeEach(() => {
    sandbox = sinon.createSandbox()
    onSubmitStub = sandbox.stub()
  })

  it("passes onSubmit to Formik", () => {
    const wrapper = renderForm()

    assert.equal(wrapper.find("Formik").props().onSubmit, onSubmitStub)
  })

  it("renders the form", () => {
    const wrapper = renderForm()

    const form = wrapper.find("Formik").dive()
    assert.ok(findFormikFieldByName(form, "couponCode").exists())
    assert.ok(form.find("button[type='submit']").exists())
  })

  it("does not render the error", () => {
    const wrapper = renderForm()
    const form = wrapper.find("Formik").dive()
    assert.ok(!form.find("div#couponCodeError").exists())
  })

  it("does not render the overwrite warning text when there aren't discounts", () => {
    while (discounts.length > 0) {
      discounts.pop()
    }

    const wrapper = renderForm()
    const form = wrapper.find("Formik").dive()
    assert.ok(!form.find("div#codeApplicationWarning").exists())
  })

  it("renders the overwrite warning text if there's a discount applied already", () => {
    // it just checks for discounts at all; it doesn't actually use this data
    discounts.push("a discount")

    const wrapper = renderForm()
    const form = wrapper.find("Formik").dive()
    assert.ok(form.find("div#codeApplicationWarning").exists())
  })
})
