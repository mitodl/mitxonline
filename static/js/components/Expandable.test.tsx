import { assert } from "chai"
import { shallow } from "enzyme"
import React from "react"
import { shouldIf } from "../lib/test_utils"
import Expandable from "./Expandable"

describe("Expandable", () => {
  it("should toggle the explanation text", () => {
    const title = "title"
    const children = "children"
    const wrapper = shallow<Expandable>(
      <Expandable title={title}>{children}</Expandable>
    )
    assert.isFalse(wrapper.state().expanded)
    wrapper.find(".header").simulate("click")
    assert.isTrue(wrapper.state().expanded)
    wrapper.find(".header").simulate("click")
    assert.isFalse(wrapper.state().expanded)
  })
  ;[true, false].forEach(expanded => {
    it(`${shouldIf(expanded)} render the explanation text`, () => {
      const title = "title"
      const children = "children"
      const wrapper = shallow(<Expandable title={title}>{children}</Expandable>)
      wrapper.setState({
        expanded
      })
      assert.equal(wrapper.find(".body").text(), expanded ? children : "")
    })
  })
})
