// @flow
import React from "react"
import { assert } from "chai"
import { mount } from "enzyme"
import { Formik } from "formik"

import {
  LegalAddressComplianceFields,
  NAME_REGEX,
  complianceAddressValidation,
  needsComplianceInfo
} from "./ProfileFormFields"

describe("ProfileFormFields", () => {
  const nameRegex = new RegExp(NAME_REGEX)
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
    it("Name regex does not match when name begins with invalid character.", () => {
      const value = `${validCharacter}Name`
      assert.isFalse(nameRegex.test(value))
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
    it("Name regex does not match when invalid character exists in name.", () => {
      const value = `Name${invalidCharacter}`
      assert.isFalse(nameRegex.test(value))
    })
  })
  ;["", "~", "!", "@", "&", "+", ":", "'", ".", "?", ",", "-"].forEach(
    validCharacter => {
      it(`Name regex does match for valid name value: Name${validCharacter}`, () => {
        const value = `Name${validCharacter}`
        assert.isTrue(nameRegex.test(value))
      })
    }
  )

  describe("needsComplianceInfo", () => {
    const user = (country, missing) => ({
      is_authenticated:          true,
      legal_address:             { country },
      compliance_missing_fields: missing
    })

    ;[
      ["nothing is missing", user("FR", []), false],
      [
        "only state/postal are missing outside US/CA",
        user("FR", ["postal_code", "state"]),
        false
      ],
      ["state/postal are missing in the US", user("US", ["postal_code"]), true],
      ["an address field is missing", user("FR", ["city"]), true],
      ["the user is anonymous", { is_authenticated: false }, false],
      ["there is no user", null, false]
    ].forEach(([desc, currentUser, expected]) => {
      it(`returns ${String(expected)} when ${desc}`, () => {
        assert.equal(needsComplianceInfo(currentUser), expected)
      })
    })
  })

  describe("complianceAddressValidation", () => {
    const values = (legalAddress = {}) => ({
      legal_address: {
        country:          "FR",
        first_name:       "Test",
        last_name:        "User",
        street_address_1: "1 Rue",
        city:             "Paris",
        postal_code:      "",
        ...legalAddress
      },
      user_profile: { year_of_birth: 1990 }
    })

    ;[
      ["a complete non-US address", values(), true],
      ["a blank city", values({ city: " " }), false],
      [
        "a US address without a state",
        values({ country: "US", state: "", postal_code: "02139" }),
        false
      ],
      [
        "a US address without a postal code",
        values({ country: "US", state: "US-MA" }),
        false
      ],
      [
        "a complete US address",
        values({ country: "US", state: "US-MA", postal_code: "02139" }),
        true
      ]
    ].forEach(([desc, formValues, expected]) => {
      it(`${expected ? "accepts" : "rejects"} ${desc}`, async () => {
        assert.equal(
          await complianceAddressValidation.isValid(formValues),
          expected
        )
      })
    })
  })

  describe("LegalAddressComplianceFields", () => {
    const renderFields = legalAddress => {
      const values = { legal_address: legalAddress }
      return mount(
        <Formik initialValues={values} onSubmit={() => undefined}>
          {({ errors, values }) => (
            <LegalAddressComplianceFields errors={errors} values={values} />
          )}
        </Formik>
      )
    }
    const shownFields = wrapper =>
      wrapper.find("input").map(input => input.prop("name"))

    it("shows only the fields that are empty", () => {
      const wrapper = renderFields({
        country:          "US",
        first_name:       "Test",
        last_name:        "",
        street_address_1: "1 Main St",
        city:             "",
        postal_code:      ""
      })
      assert.deepEqual(shownFields(wrapper), [
        "legal_address.last_name",
        "legal_address.city",
        "legal_address.postal_code"
      ])
    })

    it("limits each input to the length the server accepts", () => {
      const wrapper = renderFields({
        country:          "US",
        first_name:       "",
        last_name:        "",
        street_address_1: "",
        city:             "",
        postal_code:      ""
      })
      assert.deepEqual(
        wrapper.find("input").map(input => input.prop("maxLength")),
        [60, 60, 255, 255, 20]
      )
    })

    it("hides the postal code outside US/CA", () => {
      const wrapper = renderFields({
        country:          "FR",
        first_name:       "Test",
        last_name:        "User",
        street_address_1: "",
        city:             "Paris",
        postal_code:      ""
      })
      assert.deepEqual(shownFields(wrapper), ["legal_address.street_address_1"])
    })
  })
})
