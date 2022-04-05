// @flow
import React from "react"
import { assert } from "chai"
import { shallow } from "enzyme"

import InstituteLogo from "./InstituteLogo"

describe("InstituteLogo component", () => {
  it("renders the component", () => {
    const wrapper = shallow(<InstituteLogo />)

    const title = wrapper.find("title")
    assert.exists(title)
    assert.equal(title.text(), "Institute Logo")
    const desc = wrapper.find("desc")
    assert.exists(desc)
    assert.equal(desc.text(), "MIT Logo")
  })
})
