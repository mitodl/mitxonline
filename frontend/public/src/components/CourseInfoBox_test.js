// @flow
import React from "react"
import { assert } from "chai"
import { shallow } from "enzyme"

import CourseInfoBox from "./CourseInfoBox"
import { makeCourseDetailNoRuns } from "../factories/course"
import { makeUser } from "../factories/user"

describe("CourseInfoBox", () => {
  let course, defaultProps

  beforeEach(() => {
    course = {
      ...makeCourseDetailNoRuns(),
      programs: [
        {
          readable_id: "program-v1:MITx+DEDP",
          title:       "Data, Economics, and Design of Policy"
        }
      ]
    }
    defaultProps = {
      courses:              [course],
      currentUser:          makeUser(),
      enrollableCourseRuns: [],
      setCurrentCourseRun:  () => Promise.resolve()
    }
  })

  const render = (props = {}) =>
    shallow(<CourseInfoBox {...defaultProps} {...props} />)

  it("links to the program's Learn URL, not an internal mitxonline path", () => {
    const wrapper = render()
    const programLink = wrapper.find(".program-info-box a.info-link")

    assert.equal(
      programLink.prop("href"),
      "https://learn.mit.edu/programs/program-v1:MITx+DEDP"
    )
  })

  it("uses SETTINGS.mit_learn_base_url when set, instead of the default", () => {
    global.SETTINGS.mit_learn_base_url = "https://rc.learn.mit.edu"
    const wrapper = render()
    const programLink = wrapper.find(".program-info-box a.info-link")

    assert.equal(
      programLink.prop("href"),
      "https://rc.learn.mit.edu/programs/program-v1:MITx+DEDP"
    )
  })

  it("renders nothing extra when the course has no programs", () => {
    const wrapper = render({
      courses: [{ ...makeCourseDetailNoRuns(), programs: [] }]
    })

    assert.isFalse(wrapper.exists(".program-info-box"))
  })
})
