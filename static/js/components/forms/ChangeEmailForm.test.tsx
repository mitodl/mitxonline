import { assert } from "chai"
import { shallow } from "enzyme"
import { Formik } from "formik"
import React from "react"
import sinon from "sinon"
import { makeUser } from "../../factories/user"
import { findFormikFieldByName } from "../../lib/test_utils"
import ChangeEmailForm from "./ChangeEmailForm"

describe("ChangeEmailForm", () => {
  let sandbox: sinon.SinonSandbox, onSubmitStub: sinon.SinonStub
  const user = makeUser()

  const renderForm = () =>
    shallow(<ChangeEmailForm onSubmit={onSubmitStub} user={user} />)

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
    assert.ok(findFormikFieldByName(form, "email").exists())
    assert.ok(findFormikFieldByName(form, "confirmPassword").exists())
    assert.ok(form.find("button[type='submit']").exists())
  })
  it("confirm password is required to change the email address", async () => {
    const wrapper = renderForm()

    try {
      await wrapper.find(Formik).prop("validate")!(
        {
          email:           "abc@example.com",
          confirmPassword: ""
        },
        // @ts-ignore
        {
          context: {
            currentEmail: "abc@example.com"
          }
        }
      )
    } catch (errors: any) {
      assert.equal(
        errors.confirmPassword,
        "Confirm Password is a required field"
      )
    }
  })
})
