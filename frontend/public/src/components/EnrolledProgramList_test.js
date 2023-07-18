// @flow
import React from "react"

import { assert } from "chai"
import { shallow } from "enzyme"

import EnrolledProgramList from "./EnrolledProgramList"
import IntegrationTestHelper from "../util/integration_test_helper"
import { makeProgramEnrollment } from "../factories/course"

describe("EnrolledProgramList", () => {
  let helper, renderedCard, userEnrollments, toggleProgramDrawer

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    userEnrollments = [makeProgramEnrollment(), makeProgramEnrollment()]
    toggleProgramDrawer = helper.sandbox.stub().returns(Function)

    renderedCard = () =>
      shallow(
        <EnrolledProgramList
          enrollments={userEnrollments}
          toggleDrawer={toggleProgramDrawer}
          onUnenroll={null}
        ></EnrolledProgramList>
      )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("renders the card", async () => {
    userEnrollments = []
    const inner = await renderedCard()

    assert.isOk(inner)
  })

  it("shows a message if the user has no enrollments", async () => {
    userEnrollments = []
    const inner = await renderedCard()

    const enrolledItems = inner.find(".no-enrollments")
    assert.lengthOf(enrolledItems, 1)
    assert.isTrue(
      enrolledItems
        .at(0)
        .text()
        .includes("You are not enrolled")
    )
  })
})
