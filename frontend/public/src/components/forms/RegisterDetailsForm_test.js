// @flow
import React from "react"
import sinon from "sinon"
import { assert } from "chai"
import { mount } from "enzyme"

import RegisterDetailsForm from "./RegisterDetailsForm"

import { findFormikFieldByName } from "../../lib/test_utils"
import { makeCountries } from "../../factories/user"

describe("RegisterDetailsForm", () => {
  let sandbox, onSubmitStub

  const countries = makeCountries()

  const renderForm = () =>
    mount(<RegisterDetailsForm onSubmit={onSubmitStub} countries={countries} />)

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

    const form = wrapper.find("Formik")
    assert.ok(findFormikFieldByName(form, "name").exists())
    assert.ok(findFormikFieldByName(form, "password").exists())
    assert.ok(form.find("button[type='submit']").exists())
  })

  //
  ;[
    ["name", "name"],
    ["legal_address.first_name", "given-name"],
    ["legal_address.last_name", "family-name"],
    ["legal_address.country", "country"]
  ].forEach(([formFieldName, autoCompleteName]) => {
    it(`validates that autoComplete=${autoCompleteName} for field ${formFieldName}`, async () => {
      const wrapper = renderForm()
      const form = wrapper.find("Formik")
      assert.equal(
        findFormikFieldByName(form, formFieldName).prop("autoComplete"),
        autoCompleteName
      )
    })
  })
})
