// @flow
import React from "react"
import sinon from "sinon"
import { assert } from "chai"
import { mount } from "enzyme"
import wait from "waait"

import RegisterDetailsForm from "./RegisterDetailsForm"

import {
  findFormikFieldByName,
  findFormikErrorByName
} from "../../lib/test_utils"
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
    ["password", "", "Password is a required field"],
    ["password", "pass", "Password must be at least 8 characters"],
    ["password", "passwor", "Password must be at least 8 characters"],
    ["password", "password123", null],
    [
      "password",
      "password",
      "Password must contain at least one letter and number"
    ],
    ["name", "", "Full Name is a required field"],
    ["name", "  ", "Full Name is a required field"],
    ["name", "Jane", null],
    ["username", "", "Username is a required field"],
    ["username", "  ", "Username is a required field"],
    ["username", "ab", "Username must be at least 3 characters"],
    [
      "username",
      "0123456789012345678901234567890",
      "Username must be at most 30 characters"
    ],
    [
      "username",
      "ábc-dèf-123",
      "Username can only contain letters, numbers and the following characters: @_+-"
    ],
    ["legal_address.first_name", "", "First Name is a required field"],
    ["legal_address.last_name", "", "Last Name is a required field"]
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

  // Tests name regex for first & last name
  const invalidNameMessage =
    "Name cannot start with a special character (~!@&)(+:'.?/,`-), and cannot contain any of (/^$#*=[]`%_;<>{}|\")"
  ;["legal_address.first_name", "legal_address.last_name"].forEach(
    fieldName => {
      const wrapper = renderForm()
      const field = wrapper.find(`input[name="${fieldName}"]`)

      // List of valid character but they couldn't exist in the start of name
      ;[
        "~",
        "!",
        "@",
        "&",
        ")",
        "(",
        "+",
        ":",
        ".",
        "?",
        "/",
        ",",
        "`",
        "-"
      ].forEach(validCharacter => {
        it(`validates the field name=${fieldName}, value=${JSON.stringify(
          `${validCharacter}Name`
        )} and expects error=${JSON.stringify(
          invalidNameMessage
        )}`, async () => {
          // Prepend the character to start of the name value
          const value = `${validCharacter}Name`
          field.simulate("change", {
            persist: () => {},
            target:  { name: fieldName, value: value }
          })
          field.simulate("blur")
          await wait()
          wrapper.update()
          assert.deepEqual(
            findFormikErrorByName(wrapper, fieldName).text(),
            invalidNameMessage
          )
        })
      })
      // List of invalid characters that cannot exist anywhere in name
      ;[
        "/",
        "^",
        "$",
        "#",
        "*",
        "=",
        "[",
        "]",
        "`",
        "%",
        "_",
        ";",
        "<",
        ">",
        "{",
        "}",
        '"',
        "|"
      ].forEach(invalidCharacter => {
        it(`validates the field name=${fieldName}, value=${JSON.stringify(
          `${invalidCharacter}Name${invalidCharacter}`
        )} and expects error=${JSON.stringify(
          invalidNameMessage
        )}`, async () => {
          // Prepend the character to start if the name value
          const value = `${invalidCharacter}Name${invalidCharacter}`
          field.simulate("change", {
            persist: () => {},
            target:  { name: fieldName, value: value }
          })
          field.simulate("blur")
          await wait()
          wrapper.update()
          assert.deepEqual(
            findFormikErrorByName(wrapper, fieldName).text(),
            invalidNameMessage
          )
        })
      })
    }
  )
})
