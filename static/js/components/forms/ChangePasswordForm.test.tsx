import { assert } from "chai"
import { shallow } from "enzyme"
import React from "react"
import sinon from "sinon"
import { findFormikFieldByName } from "../../lib/test_utils"
import ChangePasswordForm from "./ChangePasswordForm"

describe("ChangePasswordForm", () => {
  let sandbox, onSubmitStub: sinon.SinonStub

  const renderForm = () =>
    shallow(<ChangePasswordForm onSubmit={onSubmitStub} />)

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
    assert.ok(findFormikFieldByName(form, "oldPassword").exists())
    assert.ok(findFormikFieldByName(form, "newPassword").exists())
    assert.ok(findFormikFieldByName(form, "confirmPassword").exists())
    assert.ok(form.find("button[type='submit']").exists())
  })
})
