import React from "react"
import {
  formatPrettyDate,
  emptyOrNil,
  getFlexiblePriceForProduct,
  formatLocalePrice
} from "../lib/util"
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

    const isArchived = moment().isAfter(run.end_date)

    const startDate =
      run && !emptyOrNil(run.start_date) && !run.is_self_paced && !isArchived
        ? moment(new Date(run.start_date))
        : null

    return (
      <>
        <div className="enrollment-info-box componentized">
          <div className="row d-flex align-self-stretch callout callout-warning">
            <i className="material-symbols-outlined warning col-1">error</i>
            <p className="col-11">This course is no longer active, but you can still enroll and access selected content.</p>
          </div>
          <div className="row d-flex align-items-center">
            <div className="enrollment-info-icon">
              <img
                src="/static/images/products/start-date.png"
                alt="Course Timing"
              />
            </div>
            <div className="enrollment-info-text">
              {startDate ? formatPrettyDate(startDate) : isArchived ? "Course content available anytime" : "Start Anytime"}
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
                    <div className="enrollment-effort">
                      {course.page.effort}
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
                  Certificate track:{" "}
                  {formatLocalePrice(getFlexiblePriceForProduct(product))}
                  {run.upgrade_deadline ? (
                    <>
                      <div className="text-danger">
                        Payment deadline:{" "}
                        {formatPrettyDate(moment(run.upgrade_deadline))}
                      </div>
                    </>
                  ) : null}
                </>
              ) : (
                "No certificate available."
              )}
              <div>
                <a
                  target="_blank"
                  rel="noreferrer"
                  href="https://mitxonline.zendesk.com/hc/en-us/articles/16928404973979-Does-MITx-Online-offer-free-certificates-"
                >
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
                </div>) : null}
            </div>
          </div>
        </div>
        {course && course.programs && course.programs.length > 0 ? (
          <div className="program-info-box">
            <strong>
              Part of the following program
              {course.programs.length === 1 ? null : "s"}
            </strong>

            <ul>
              {course.programs.map(elem => (
                <>
                  <li>
                    {" "}
                    <a href={`/programs/${elem.readable_id}/`}>{elem.title}</a>
                  </li>
                </>
              ))}
            </ul>
          </div>
        ) : null}
      </>
    )
  }
}
