// @flow
import React from "react"

import { assert } from "chai"
import { shallow } from "enzyme"


import EnrolledCourseList from "./EnrolledCourseList"
import IntegrationTestHelper from "../util/integration_test_helper"
import { makeCourseRunEnrollment } from "../factories/course"

describe("EnrolledCourseList", () => {
  let helper, renderedCard, userEnrollments

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    userEnrollments = [makeCourseRunEnrollment(), makeCourseRunEnrollment()]

    renderedCard = () => shallow(
      <EnrolledCourseList enrollments={userEnrollments}></EnrolledCourseList>
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
