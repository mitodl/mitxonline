// @flow
import React from "react"
import sinon from "sinon"
import { assert } from "chai"
import { mount } from "enzyme"

import AddlProfileFieldsForm from "./AddlProfileFieldsForm"

describe("AddlProfileFieldsForm", () => {
  const user = {
    name:          "Test User",
    email:         "test@example.com",
    legal_address: {
      country:          "FR",
      first_name:       "Test",
      last_name:        "User",
      street_address_1: "1 Rue",
      street_address_2: "",
      city:             "",
      state:            "",
      postal_code:      ""
    },
    user_profile: { year_of_birth: 1990 }
  }
  const countries = [{ code: "FR", name: "France", states: [] }]

  const renderForm = (props = {}) =>
    mount(
      // $FlowFixMe: partial user is enough for the form
      <AddlProfileFieldsForm user={user} countries={countries} {...props} />
    )

  it("adds the empty compliance fields and requires them when asked to", async () => {
    const onSubmit = sinon.stub()
    const wrapper = renderForm({ onSubmit, requireComplianceFields: true })

    assert.isTrue(wrapper.exists('input[name="legal_address.city"]'))
    wrapper.find("form").simulate("submit")
    await new Promise(resolve => setTimeout(resolve, 0))
    wrapper.update()
    assert.isTrue(wrapper.exists("#city-error"))
    sinon.assert.notCalled(onSubmit)
  })

  it("leaves the compliance fields out by default", () => {
    const wrapper = renderForm({ onSubmit: sinon.stub() })

    assert.isFalse(wrapper.exists('input[name="legal_address.city"]'))
  })
})
