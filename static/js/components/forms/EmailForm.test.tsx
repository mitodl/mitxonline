import { assert } from "chai"
import { shallow } from "enzyme"
import React, { ReactNode } from "react"
import sinon from "sinon"
import { findFormikFieldByName } from "../../lib/test_utils"
import EmailForm from "./EmailForm"

describe("EmailForm", () => {
  let sandbox: sinon.SinonSandbox, onSubmitStub: sinon.SinonStub

  const renderForm = (children?: ReactNode) =>
    shallow(
      <EmailForm
        onSubmit={onSubmitStub}
        {...(children
          ? {
            children: children
          }
          : {})}
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
    const emailField = findFormikFieldByName(form, "email")
    assert.ok(emailField.exists())
    assert.equal(emailField.prop("autoComplete"), "email")
    assert.ok(form.find("button[type='submit']").exists())
  })
  it("renders child elements if they are passed in", () => {
    const wrapper = renderForm(<div id="test-child">child element</div>)
    const form = wrapper.find("Formik").dive()
    const testChild = form.find("div#test-child")
    assert.ok(testChild.exists())
    assert.equal(testChild.at(0).text(), "child element")
    assert.equal(testChild.parent().prop("className"), "form-group")
  })
})
