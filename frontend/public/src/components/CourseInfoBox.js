import React from "react"
import { formatPrettyDate, emptyOrNil } from "../lib/util"
import moment from "moment-timezone"

import type { BaseCourseRun } from "../flow/courseTypes"

type CourseInfoBoxProps = {
  courses: Array<BaseCourseRun>
}

export default class CourseInfoBox extends React.PureComponent<CourseInfoBoxProps> {
  render() {
    const { courses } = this.props

    if (!courses || courses.length < 1) {
      return null
    }

    const course = courses[0]

    const run = course.next_run_id
      ? course.courseruns.find(elem => elem.id === course.next_run_id)
      : course.courseruns[0]

    const product = run && run.products.length > 0 && run.products[0]

    const startDate =
      run && !emptyOrNil(run.start_date)
        ? moment(new Date(run.start_date))
        : null

    return (
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
        {course && course.page ? (
          <div className="row d-flex align-items-top">
            <div className="enrollment-info-icon">
              <img
                src="/static/images/products/effort.png"
                alt="Expected Length and Effort"
              />
            </div>
            <div className="enrollment-info-text">
              {course.page.length}
              {run && run.is_self_paced ? (
                <span className="badge badge-pacing">SELF-PACED</span>
              ) : null}
              {course.page.effort ? (
                <>
                  <div className="enrollment-effort">{course.page.effort}</div>
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
                {course.page.financial_assistance_form_url ? (
                  <div>
                    <a
                      target="_blank"
                      rel="noreferrer"
                      href={course.page.financial_assistance_form_url}
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
    )
  }
}
