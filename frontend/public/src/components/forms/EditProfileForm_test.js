// @flow
import React from "react"
import sinon from "sinon"
import { assert } from "chai"
import { mount } from "enzyme"

import EditProfileForm from "./EditProfileForm"
import { findFormikFieldByName } from "../../lib/test_utils"
import { makeCountries, makeUser } from "../../factories/user"
import * as utils from "../../lib/util"

describe("EditProfileForm", () => {
  let sandbox, onSubmitStub, checkFeatureFlagStub

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
    checkFeatureFlagStub = sandbox.stub(utils, "checkFeatureFlag").returns(true)
  })

  afterEach(() => {
    checkFeatureFlagStub.restore()
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
    assert.ok(
      findFormikFieldByName(form, "user_profile.year_of_birth").exists()
    )
    assert.ok(form.find("button[type='submit']").exists())
  })

  it("renders the form and displays the additional fields if they're set", () => {
    const wrapper = renderForm()
    const form = wrapper.find("Formik")

    assert.ok(findFormikFieldByName(form, "legal_address.state").exists())
    assert.ok(findFormikFieldByName(form, "user_profile.type_is_professional"))
    assert.ok(findFormikFieldByName(form, "user_profile.company").exists())
  })
})
