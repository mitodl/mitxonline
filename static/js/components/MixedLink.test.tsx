import { assert } from "chai"
import React from "react"
import {
  AppTypeContext,
  MIXED_APP_CONTEXT,
  SPA_APP_CONTEXT
} from "../contextDefinitions"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import MixedLink from "./MixedLink"

describe("MixedLink component", () => {
  let helper: IntegrationTestHelper, render: TestRenderer
  const testDest = "/some/url",
    testLinkText = "link",
    testAriaLabel = "aria link"

  const TestComponent = ({ appType, ...props }: any) => (
    <AppTypeContext.Provider value={appType}>
      <MixedLink {...props} />
    </AppTypeContext.Provider>
  )

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    render = helper.configureRenderer(TestComponent)
  })

  afterEach(() => {
    helper.cleanup()
  })

  it(`renders a react router Link when the app type is '${SPA_APP_CONTEXT}'`, async () => {
    const { wrapper } = await render({
      appType:      SPA_APP_CONTEXT,
      dest:         testDest,
      children:     testLinkText,
      "aria-label": testAriaLabel
    })
    const link = wrapper.find("Link")
    assert.isTrue(link.exists())
    const linkProps = link.props()
    assert.equal(linkProps.to, testDest)
    assert.equal(linkProps.children, testLinkText)
    assert.equal(linkProps["aria-label"], testAriaLabel)
  })
  it(`renders a normal anchor link when the app type is '${MIXED_APP_CONTEXT}'`, async () => {
    const { wrapper } = await render({
      appType:      MIXED_APP_CONTEXT,
      dest:         testDest,
      children:     testLinkText,
      "aria-label": testAriaLabel
    })
    const link = wrapper.find("a")
    assert.isTrue(link.exists())
    const linkProps = link.props()
    assert.equal(linkProps.href, testDest)
    assert.equal(linkProps.children, testLinkText)
    assert.equal(linkProps["aria-label"], testAriaLabel)
  })
})
