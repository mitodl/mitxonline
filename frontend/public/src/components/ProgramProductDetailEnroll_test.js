/* global SETTINGS: false */
// @flow
import { assert } from "chai"

import IntegrationTestHelper from "../util/integration_test_helper"
import ProgramProductDetailEnroll, {
  ProgramProductDetailEnroll as InnerProgramProductDetailEnroll
} from "./ProgramProductDetailEnroll"

import {
  makeCourseDetailWithRuns,
  makeCourseRunDetailWithProduct,
  makeProgramWithReqTree,
  makeProgramEnrollment
} from "../factories/course"

import { makeUser } from "../factories/user"

describe("ProgramProductDetailEnroll", () => {
  let helper,
    renderPage,
    courseRun,
    course,
    currentUser,
    programs,
    programEnrollments

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    courseRun = makeCourseRunDetailWithProduct()
    course = makeCourseDetailWithRuns()
    currentUser = makeUser()
    programs = [makeProgramWithReqTree()]
    programEnrollments = [makeProgramEnrollment()]

    renderPage = helper.configureMountRenderer(
      ProgramProductDetailEnroll,
      InnerProgramProductDetailEnroll,
      {
        entities: {
          programId:          "program-id",
          programs:           programs,
          programEnrollments: programEnrollments,
          courseRuns:         [courseRun],
          courses:            [course],
          currentUser:        currentUser
        }
      },
      {}
    )
    SETTINGS.features = {
      "mitxonline-new-product-page": true
    }
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("renders anything", async () => {
    const { inner } = await renderPage({
      queries: {
        courseRuns: {
          isPending: true
        },
        programs: {
          isPending: true
        },
        program_enrollments: {
          isPending: true
        }
      }
    })

    assert.isOk(inner.find("ProgramProductDetailEnroll"))
  })

  it("renders a Loader component", async () => {
    const { inner } = await renderPage({
      queries: {
        courseRuns: {
          isPending: true
        },
        programs: {
          isPending: true
        },
        program_enrollments: {
          isPending: true
        }
      }
    })

    const loader = inner.find("Loader").first()
    assert.isOk(loader.exists())
    assert.isTrue(loader.props().isLoading)
  })

  it("checks for enroll now button", async () => {
    const { inner } = await renderPage()

    assert.equal(
      inner
        .find(".enroll-now")
        .at(0)
        .text(),
      "Enroll now"
    )
  })

  it("shows course chooser dialog when Enroll Now is clicked", async () => {
    const { inner } = await renderPage()

    const enrollBtn = inner.find(".enroll-now").at(0)
    assert.isTrue(enrollBtn.exists())
    await enrollBtn.prop("onClick")()

    const modal = inner.find(".upgrade-enrollment-modal")
    assert.isOk(modal)
  })
})
