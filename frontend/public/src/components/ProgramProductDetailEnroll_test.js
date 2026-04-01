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

    renderPage = helper.configureShallowRenderer(
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

    assert.equal(inner.find(".enroll-now").at(0).text(), "Enroll now")
  })

  it("shows course chooser dialog when Enroll Now is clicked", async () => {
    const { inner } = await renderPage()

    const enrollBtn = inner.find(".enroll-now").at(0)
    assert.isTrue(enrollBtn.exists())
    await enrollBtn.prop("onClick")()

    const modal = inner.find(".upgrade-enrollment-modal")
    assert.isOk(modal)
  })

  it("calls program enrollment API when Enroll Now is clicked", async () => {
    const program = programs[0]
    const createProgramEnrollmentStub = helper.sandbox.stub().resolves({})

    const { inner } = await renderPage()
    inner.setProps({ createProgramEnrollment: createProgramEnrollmentStub })

    const enrollBtn = inner.find(".enroll-now").at(0)
    assert.isTrue(enrollBtn.exists())
    await enrollBtn.prop("onClick")()

    assert.isTrue(createProgramEnrollmentStub.calledOnceWithExactly(program.id))

    const modal = inner.find("#upgrade-enrollment-dialog")
    assert.isTrue(modal.find("select.form-control").exists())

    assert.isFalse(modal.find("button.enroll-now-free").exists())

    // toggle the dialog back and check if the program enrollment api was not called again
    await modal.prop("toggle")()
    inner.update()
    assert.isFalse(inner.find("#upgrade-enrollment-dialog").prop("isOpen"))
    assert.strictEqual(createProgramEnrollmentStub.callCount, 1)
  })
})
