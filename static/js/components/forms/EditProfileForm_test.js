// @flow
import React from "react"
import sinon from "sinon"
import { assert } from "chai"
import { mount } from "enzyme"
import wait from "waait"

import EditProfileForm from "./EditProfileForm"
import {
  findFormikFieldByName,
  findFormikErrorByName
} from "../../lib/test_utils"
import { makeCountries, makeUser } from "../../factories/user"

describe("EditProfileForm", () => {
  let sandbox, onSubmitStub

  const countries = makeCountries()
  const user = makeUser()

  const renderForm = () =>
    mount(
      <EditProfileForm
        onSubmit={onSubmitStub}
        countries={countries}
        user={user}
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
    const form = wrapper.find("Formik")
    assert.ok(findFormikFieldByName(form, "name").exists())
    assert.isNotOk(findFormikFieldByName(form, "password").exists())
    assert.ok(findFormikFieldByName(form, "legal_address.first_name").exists())
    assert.ok(findFormikFieldByName(form, "legal_address.last_name").exists())
    assert.ok(findFormikFieldByName(form, "legal_address.country").exists())
    assert.ok(form.find("button[type='submit']").exists())
  })

  //
  ;[
    ["legal_address.first_name", "", "First Name is a required field"],
    ["legal_address.first_name", "  ", "First Name is a required field"],
    ["legal_address.first_name", "Jane", null],
    ["legal_address.last_name", "", "Last Name is a required field"],
    ["legal_address.last_name", "  ", "Last Name is a required field"],
    ["legal_address.last_name", "Doe", null]
  ].forEach(([name, value, errorMessage]) => {
    it(`validates the field name=${name}, value=${JSON.stringify(
      value
    )} and expects error=${JSON.stringify(errorMessage)}`, async () => {
      const wrapper = renderForm()

      const input = wrapper.find(`input[name="${name}"]`)
      input.simulate("change", { persist: () => {}, target: { name, value } })
      input.simulate("blur")
      await wait()
      wrapper.update()
      assert.deepEqual(
        findFormikErrorByName(wrapper, name).text(),
        errorMessage
      )
    })
  })
})
