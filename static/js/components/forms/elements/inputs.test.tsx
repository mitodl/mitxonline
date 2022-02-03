import { assert } from "chai"
import { shallow } from "enzyme"
import React from "react"
import { isIf } from "../../../lib/test_utils"
import { EmailInput, PasswordInput, TextInput } from "./inputs"

describe("Form input", () => {
  describe("for text", () => {
    const fieldName = "myField"
    const defaultProps = {
      field: {
        name: fieldName
      },
      form: {
        touched: {
          [fieldName]: false
        },
        errors: {
          [fieldName]: null
        }
      }
    }
    it("has the right input type", () => {
      // @ts-ignore
      const textInput = shallow(<TextInput {...defaultProps} />)
      assert.equal(textInput.prop("type"), "text")
      // @ts-ignore
      const emailInput = shallow(<EmailInput {...defaultProps} />)
      assert.equal(emailInput.prop("type"), "email")
      // @ts-ignore
      const passwordInput = shallow(<PasswordInput {...defaultProps} />)
      assert.equal(passwordInput.prop("type"), "password")
    })
    ;([
      ["some-class", false, "some-class "],
      ["", true, " errored"],
      ["some-class", true, "some-class errored"]
    ] as [string, boolean, string][]).forEach(
      ([className, isErrored, expClassName]) => {
        it(`has the right class names if class ${isIf(
          !!className
        )} specified and ${isIf(isErrored)} in error state`, () => {
          const props = {
            ...defaultProps,
            form: {
              touched: {
                [fieldName]: isErrored
              },
              errors: {
                [fieldName]: isErrored ? "ERROR" : null
              }
            }
          }
          const textInput = shallow(
            // @ts-ignore
            <TextInput className={className} {...props} />
          )
          assert.equal(textInput.prop("className"), expClassName)
        })
      }
    )
  })
})
