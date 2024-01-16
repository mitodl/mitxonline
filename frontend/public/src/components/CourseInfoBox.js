import React from "react"
import {
  formatPrettyDate,
  emptyOrNil,
  getFlexiblePriceForProduct,
  formatLocalePrice,
  getStartDateText
} from "../lib/util"
import { getFirstRelevantRun } from "../lib/courseApi"
import moment from "moment-timezone"

import type { BaseCourseRun } from "../flow/courseTypes"
import { EnrollmentFlaggedCourseRun, RunEnrollment } from "../flow/courseTypes"
import type { CurrentUser } from "../flow/authTypes"

type CourseInfoBoxProps = {
  courses: Array<BaseCourseRun>,
  courseRuns: ?Array<EnrollmentFlaggedCourseRun>,
  enrollments: ?Array<RunEnrollment>,
  currentUser: CurrentUser,
  toggleUpgradeDialogVisibility: () => Promise<any>,
  setCurrentCourseRun: (run: EnrollmentFlaggedCourseRun) => Promise<any>
}

export default class CourseInfoBox extends React.PureComponent<CourseInfoBoxProps> {
  state = {
    showMoreEnrollDates: false
  }
  toggleShowMoreEnrollDates() {
    this.setState({
      showMoreEnrollDates: !this.state.showMoreEnrollDates
    })
  }
  setRunEnrollDialog(run: EnrollmentFlaggedCourseRun) {
    this.props.setCurrentCourseRun(run)
    this.props.toggleUpgradeDialogVisibility()
  }

  renderEnrolledDateLink(run: EnrollmentFlaggedCourseRun) {
    return (
      <button className="more-dates-link enrolled">
        {getStartDateText(run)} - Enrolled
      </button>
    )
  }

  render() {
    const { courses, courseRuns, enrollments } = this.props

    if (!courses || courses.length < 1) {
      return null
    }

    const course = courses[0]
    const run = getFirstRelevantRun(course, courseRuns)
    const product = run && run.products.length > 0 && run.products[0]

    const isArchived =
      moment().isAfter(run.end_date) &&
      (moment().isBefore(run.enrollment_end) || emptyOrNil(run.enrollment_end))

    const startDates = []
    const moreEnrollableCourseRuns = courseRuns && courseRuns.length > 1
    if (moreEnrollableCourseRuns) {
      courseRuns.forEach((courseRun, index) => {
        if (courseRun.id !== run.id) {
          startDates.push(
            <li key={index}>
              {courseRun.is_enrolled ||
              (enrollments &&
                enrollments.find(
                  (enrollment: RunEnrollment) =>
                    enrollment.run.id === courseRun.id
                ))
                ? this.renderEnrolledDateLink(courseRun)
                : getStartDateText(courseRun, true)}
            </li>
          )
        }
      })
    }
    return (
      <>
        <div className="enrollment-info-box componentized">
          {isArchived ? (
            <div className="row d-flex align-self-stretch callout callout-warning course-archived-message">
              <i className="material-symbols-outlined warning">error</i>
              <p>
                This course is no longer active, but you can still access
                selected content.
              </p>
            </div>
          ) : null}
          <div className="row d-flex align-items-center course-timing-message">
            <div className="enrollment-info-icon" aria-level="3" role="heading">
              <img
                src="/static/images/products/start-date.png"
                alt="Course Timing"
              />
            </div>
            <div className="enrollment-info-text">
              {isArchived
                ? "Course content available anytime"
                : getStartDateText(run)}
            </div>
            {!isArchived && moreEnrollableCourseRuns ? (
              <>
                <button
                  className="more-enrollment-info"
                  onClick={() => this.toggleShowMoreEnrollDates()}
                >
                  {this.state.showMoreEnrollDates ? "Show Less" : "More Dates"}
                </button>
                {this.state.showMoreEnrollDates ? (
                  <ul className="more-dates-enrollment-list">{startDates}</ul>
                ) : null}
              </>
            ) : null}
          </div>
          {course && course.page ? (
            <div className="row d-flex align-items-top course-effort-message">
              <div
                className="enrollment-info-icon"
                aria-level="3"
                role="heading"
              >
                <img
                  src="/static/images/products/effort.png"
                  alt="Expected Length and Effort"
                />
              </div>
              <div className="enrollment-info-text">
                {course.page.length}
                {isArchived ? (
                  <>
                    <span className="badge badge-pacing">ARCHIVED</span>
                    <a
                      className="pacing-faq-link float-right"
                      href="https://mitxonline.zendesk.com/hc/en-us/articles/21995114519067-What-are-Archived-courses-on-MITx-Online-"
                    >
                      What's this?
                    </a>
                  </>
                ) : run && run.is_self_paced ? (
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
          <div className="row d-flex align-items-center course-pricing-message">
            <div className="enrollment-info-icon" aria-level="3" role="heading">
              <img src="/static/images/products/cost.png" alt="Cost" />
            </div>
            <div className="enrollment-info-text">
              <b>Free</b>
            </div>
          </div>
          <div className="row d-flex align-items-top course-certificate-message">
            <div className="enrollment-info-icon" aria-level="3" role="heading">
              <img
                src="/static/images/products/certificate.png"
                alt="Certificate Track Information"
              />
            </div>
            <div className="enrollment-info-text">
              {product && !isArchived ? (
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
                </div>
              ) : null}
            </div>
          </div>
        </div>
        {course && course.programs && course.programs.length > 0 ? (
          <div className="program-info-box">
            <h3>
              Part of the following program
              {course.programs.length === 1 ? null : "s"}
            </h3>

            <ul>
              {course.programs.map(elem => (
                <li key={elem.readable_id}>
                  {" "}
                  <a href={`/programs/${elem.readable_id}/`}>{elem.title}</a>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </>
    )
  }
}
