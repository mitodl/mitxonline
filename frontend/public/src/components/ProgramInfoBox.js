import React from "react"
import { formatPrettyDate, emptyOrNil } from "../lib/util"
import moment from "moment-timezone"

import type { Program, BaseCourseRun, CourseDetailWithRuns } from "../flow/courseTypes"

type ProgramInfoBoxProps = {
  programs: Array<Program>
}

export default class ProgramInfoBox extends React.PureComponent<ProgramInfoBoxProps> {
  findFirstCourseRun() {
    const { programs } = this.props

    if (!programs || programs.length < 1) {
      return null
    }

    let courseRun: BaseCourseRun|null = null

    programs[0].courses.forEach((course: CourseDetailWithRuns) => {
      const thisNextRun = course.next_run_id
        ? course.courseruns.find(elem => elem.id === course.next_run_id)
        : course.courseruns[0]

      if (!courseRun || (emptyOrNil(courseRun.start_date && !emptyOrNil(thisNextRun.start_date)))) {
        courseRun = thisNextRun
      } else {
        if (moment(new Date(thisNextRun.start_date)) <= moment(new Date(courseRun.start_date))) {
          courseRun = thisNextRun
        }
      }
    })

    return courseRun
  }

  render() {
    const { programs } = this.props

    if (!programs || programs.length < 1) {
      return null
    }

    const program = programs[0]

    const run = this.findFirstCourseRun()

    const product = run && run.products.length > 0 && run.products[0]

    const startDate =
      run && !emptyOrNil(run.start_date)
        ? moment(new Date(run.start_date))
        : null

    return (
      <>
        <div className="enrollment-info-box">
          <div className="row d-flex align-items-center">
            <div className="enrollment-info-icon">
              <img
                src="/static/images/products/start-date.png"
                alt="Course Timing"
              />
            </div>
            <div className="enrollment-info-text">
              {startDate ? formatPrettyDate(startDate) : "Start Anytime"}
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
                  <span className="badge badge-pacing">SELF-PACED</span>
                ) : null}
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
                  Certificate track: $
                  {product.price.toLocaleString("en-us", {
                    style: "currency",
                    currency: "en-US"
                  })}
                  {run.upgrade_deadline ? (
                    <>
                      <div className="text-danger">
                        Payment deadline:{" "}
                        {formatPrettyDate(moment(run.upgrade_deadline))}
                      </div>
                    </>
                  ) : null}
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
