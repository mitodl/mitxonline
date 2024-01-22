import React from "react"
import { emptyOrNil } from "../lib/util"
import moment from "moment-timezone"

import type {
  Program,
  BaseCourseRun,
  CourseDetailWithRuns
} from "../flow/courseTypes"

type ProgramInfoBoxProps = {
  programs: Array<Program>
}

export default class ProgramInfoBox extends React.PureComponent<ProgramInfoBoxProps> {
  findFirstCourseRun() {
    const { programs } = this.props

    if (!programs || programs.length < 1) {
      return null
    }

    let courseRun: BaseCourseRun | null = null

    programs[0].courses.forEach((course: CourseDetailWithRuns) => {
      const thisNextRun = course.next_run_id
        ? course.courseruns.find(elem => elem.id === course.next_run_id)
        : course.courseruns[0]

      if (
        !courseRun ||
        emptyOrNil(courseRun.start_date && !emptyOrNil(thisNextRun.start_date))
      ) {
        courseRun = thisNextRun
      } else {
        if (
          moment(new Date(thisNextRun.start_date)) <=
          moment(new Date(courseRun.start_date))
        ) {
          courseRun = thisNextRun
        }
      }
    })

    return courseRun
  }

  getReqNode(nodeFlag: boolean = true) {
    const { programs } = this.props

    if (!programs || programs.length < 1 || !programs[0].req_tree) {
      return null
    }

    if (nodeFlag) {
      return programs[0].req_tree[0].children.find(
        elem => elem.data.node_type === "operator" && !elem.data.elective_flag
      )
    }

    return programs[0].req_tree[0].children.find(
      elem => elem.data.node_type === "operator" && elem.data.elective_flag
    )
  }

  getRequiredTitle() {
    const requiredNode = this.getReqNode()

    return requiredNode ? requiredNode.data.title : "Core Courses"
  }

  getElectiveTitle() {
    const requiredNode = this.getReqNode(false)

    return requiredNode ? requiredNode.data.title : "Electives"
  }

  render() {
    const { programs } = this.props

    if (!programs || programs.length < 1) {
      return null
    }

    const program = programs[0]

    const run = this.findFirstCourseRun()

    const product = run && run.products.length > 0 && run.products[0]

    const reqCount = program.requirements.required.length
    const electiveCount = program.requirements.electives.length
    let electiveCountPrefix = ""

    if (electiveCount > 0) {
      const electives = this.getReqNode(false)

      if (electives.data.operator !== "all_of") {
        electiveCountPrefix = `${electives.data.operator_value} of `
      }
    }

    return (
      <>
        <div className="enrollment-info-box">
          <div className="row d-flex align-items-top">
            <div className="enrollment-info-icon">
              <img
                src="/static/images/products/browser.png"
                alt="Program Requirements"
              />
            </div>
            <div className="enrollment-info-text">
              {reqCount} {this.getRequiredTitle()}: Complete All
              {electiveCount > 0 ? (
                <>
                  <br />
                  {electiveCount} {this.getElectiveTitle()}: Complete{" "}
                  {electiveCountPrefix}
                  {electiveCount}
                </>
              ) : null}
            </div>
          </div>
          {program && program.page ? (
            <div className="row d-flex align-items-top">
              <div className="enrollment-info-icon">
                <img
                  src="/static/images/products/effort.png"
                  alt="Expected Length and Effort"
                />
              </div>
              <div className="enrollment-info-text">
                {program.page.length}
                {run && run.is_self_paced ? (
                  <>
                    <span className="badge badge-pacing">SELF-PACED</span>
                    <a
                      className="pacing-faq-link float-right"
                      href="https://mitxonline.zendesk.com/hc/en-us/articles/21994872904475-What-are-Self-Paced-courses-on-MITx-Online-"
                    >
                      What's this?
                    </a>
                  </>
                ) : (
                  <>
                    <span className="badge badge-pacing">INSTRUCTOR-PACED</span>
                    <a
                      className="pacing-faq-link float-right"
                      href="https://mitxonline.zendesk.com/hc/en-us/articles/21994938130075-What-are-Instructor-Paced-courses-on-MITx-Online-"
                    >
                      What's this?
                    </a>
                  </>
                )}
                {program.page.effort ? (
                  <>
                    <div className="enrollment-effort">
                      {program.page.effort}
                    </div>
                  </>
                ) : null}
              </div>
            </div>
          ) : null}
          <div className="row d-flex align-items-center">
            <div className="enrollment-info-icon">
              <img src="/static/images/products/cost.png" alt="Cost" />
            </div>
            <div className="enrollment-info-text font-weight-bold">Free</div>
          </div>
          <div className="row d-flex align-items-top">
            <div className="enrollment-info-icon">
              <img
                src="/static/images/products/certificate.png"
                alt="Certificate Track Information"
              />
            </div>
            <div className="enrollment-info-text">
              {product ? (
                <>
                  Certificate track: {program.page.price}
                  <div>
                    <a target="_blank" rel="noreferrer" href="#">
                      What's the certificate track?
                    </a>
                  </div>
                  {program.page.financial_assistance_form_url ? (
                    <div>
                      <a
                        target="_blank"
                        rel="noreferrer"
                        href={program.page.financial_assistance_form_url}
                      >
                        Financial assistance available
                      </a>
                    </div>
                  ) : null}
                </>
              ) : (
                "No certificate available."
              )}
            </div>
          </div>
        </div>
      </>
    )
  }
}
