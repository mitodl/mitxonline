// @flow
import { assert } from "chai"
import { shallow } from "enzyme"

import { formatErrors } from "./form"

describe("form functions", () => {
  describe("formatErrors", () => {
    it("should return null if there is no error", () => {
      assert.isNull(formatErrors(null))
    })

    it("should return a div with the error string if the error is a string", () => {
      const wrapper = shallow(formatErrors("error"))
      assert.equal(wrapper.find(".error").text(), "error")
    })

    it("should return the first item in the error if there is no 'items'", () => {
      const error = ["error"]
      const wrapper = shallow(formatErrors(error))
      assert.equal(wrapper.find(".error").text(), "error")
    })
  })
})
