// @flow
import React from "react"
import sinon from "sinon"
import { assert } from "chai"
import { shallow } from "enzyme"

import ChangeEmailForm from "./ChangeEmailForm"

import { findFormikFieldByName } from "../../lib/test_utils"

import { makeUser } from "../../factories/user"

describe("ChangeEmailForm", () => {
  let sandbox, onSubmitStub

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
})
