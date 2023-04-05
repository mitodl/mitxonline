// @flow
import { assert } from "chai"

import { NAME_REGEX, fullNameRegex } from "./ProfileFormFields"

describe("ProfileFormFields", () => {
  const nameRegex = new RegExp(NAME_REGEX)
  const fullNameRegexObject = new RegExp(fullNameRegex)
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
  ;[
    "",
    "~",
    "!",
    "@",
    "&",
    ")",
    "(",
    "+",
    ":",
    "'",
    ".",
    "?",
    ",",
    "-"
  ].forEach(validCharacter => {
    it(`Name regex does match for valid name value: Name${validCharacter}`, () => {
      const value = `Name${validCharacter}`
      assert.isTrue(nameRegex.test(value))
    })
  })
  ;[
    ["John Smith", true],
    ["Jo", true],
    ["j", false],
    ["j", false],
    [
      "This is a name longer than 255 characters lrTdKUf2fqZfswelfcqCexp7tw7ALZF57fioQT408kCXpJSSlg3cPfEKLWT2dxIJW9qYOaHcxau5OQLK0btMyq16MGqMlkTqFlJqkiHvo3ivHwoXju2W3PHjQxDHQt2TuyGLL3JmlPqVICBNsheEPHgco0KFHPyE3rcc5YjTDIpCXnhQe7aivDFY95B7N00DStEK8Rd5CQ5IXRIOHQm6laKgAaCXZz",
      false
    ]
  ].forEach(([fullNameValue, regexMatch]) => {
    it("Full name regex does not match when name begins with invalid character.", () => {
      assert.equal(fullNameRegexObject.test(fullNameValue), regexMatch)
    })
  })
})
