// @flow
import React from "react"
import { assert } from "chai"
import { shallow } from "enzyme"

import Loader from "./Loader"

describe("Loader component", () => {
  const exampleChildComponent = <div>child</div>

  it("renders the child component if isLoading=false", () => {
    const wrapper = shallow(
      <Loader isLoading={false}>{exampleChildComponent}</Loader>
    )

    assert.equal(wrapper.html(), shallow(exampleChildComponent).html())
  })
})
