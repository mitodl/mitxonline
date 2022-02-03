import { shallow } from "enzyme"
import React from "react"
import { TextNotification } from "."

describe("Notification component", () => {
  it("TextNotification", () => {
    const text = "Some text"
    const wrapper = shallow(
      <TextNotification text={"Some text"} dismiss={jest.fn()} />
    )
    expect(wrapper.text()).toEqual(text)
  })
})
