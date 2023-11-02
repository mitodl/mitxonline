import React from "react"
import {
  formatPrettyDate,
  emptyOrNil,
  getFlexiblePriceForProduct,
  formatLocalePrice
} from "../lib/util"
import moment from "moment-timezone"

import type { BaseCourseRun } from "../flow/courseTypes"
import { EnrollmentFlaggedCourseRun } from "../flow/courseTypes"
import { getCookie } from "../lib/api"
import { isWithinEnrollmentPeriod } from "../lib/courseApi"
import type { CurrentUser } from "../flow/authTypes"
import { routes } from "../lib/urls"

type CourseInfoBoxProps = {
  courses: Array<BaseCourseRun>,
  courseRuns: ?Array<EnrollmentFlaggedCourseRun>,
  toggleUpgradeDialogVisibility: () => Promise<any>,
  setCurrentCourseRun: (run: EnrollmentFlaggedCourseRun) => Promise<any>,
  currentUser: CurrentUser
}

const getStartDateText = (run: BaseCourseRun, isArchived: boolean = false) => {
  if (isArchived) {
    return "Course content available anytime"
  }
  return run && !emptyOrNil(run.start_date) && !run.is_self_paced
    ? (run.start_date > moment() ? "Starts: " : "Started: ") +
        formatPrettyDate(moment(new Date(run.start_date)))
    : "Start Anytime"
}

const getStartDateForRun = (run: BaseCourseRun) => {
  return run && !emptyOrNil(run.start_date) && !run.is_self_paced
    ? formatPrettyDate(moment(new Date(run.start_date)))
    : "Start Anytime"
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

  renderEnrollNowDateLink(run: EnrollmentFlaggedCourseRun) {
    const { currentUser } = this.props
    const csrfToken = getCookie("csrftoken")

    const product = run && run.products.length > 0 && run.products[0]

    return currentUser && currentUser.id ? (
      run && isWithinEnrollmentPeriod(run) ? (
        <>
          {product && run.is_upgradable ? (
            <button
              className="more-dates-link"
              onClick={() => this.setRunEnrollDialog(run)}
            >
              {getStartDateForRun(run)}
            </button>
          ) : (
            <form action="/enrollments/" method="post">
              <input
                type="hidden"
                name="csrfmiddlewaretoken"
                value={csrfToken}
              />
              <input type="hidden" name="run" value={run ? run.id : ""} />
              <button type="submit" className="more-dates-link">
                {getStartDateForRun(run)}
              </button>
            </form>
          )}
        </>
      ) : null
    ) : (
      this.renderEnrollLoginDateLink(run)
    )
  }
  renderEnrollLoginDateLink(run: EnrollmentFlaggedCourseRun) {
    const { currentUser } = this.props

    return !currentUser || !currentUser.id ? (
      <>
        <a href={routes.login} className="more-dates-link">
          {getStartDateForRun(run)}
        </a>
      </>
    ) : null
  }
  renderEnrolledDateLink(run: EnrollmentFlaggedCourseRun) {
    return (
      <button className="more-dates-link enrolled">
        {getStartDateText(run)} - Enrolled
      </button>
    )
  }

  render() {
    const { courses, courseRuns } = this.props

    if (!courses || courses.length < 1) {
      return null
    }

    const course = courses[0]

    const run = course.next_run_id
      ? course.courseruns.find(elem => elem.id === course.next_run_id)
      : course.courseruns[0]
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
              {courseRun.is_enrolled
                ? this.renderEnrolledDateLink(courseRun)
                : this.renderEnrollNowDateLink(courseRun)}
            </li>
          )
        }
      })
    }
    return (
      <>
        <div className="enrollment-info-box componentized">
          {isArchived ? (
            <div className="row d-flex align-self-stretch callout callout-warning">
              <i className="material-symbols-outlined warning">error</i>
              <p>
                This course is no longer active, but you can still access
                selected content.
              </p>
            </div>
          ) : null}
          <div className="row d-flex align-items-center">
            <div className="enrollment-info-icon">
              <img
                src="/static/images/products/start-date.png"
                alt="Course Timing"
              />
            </div>
            <div className="enrollment-info-text">
              {getStartDateText(run, isArchived)}
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
            <div className="enrollment-info-text">
              <b>Free</b>
            </div>
          </div>
          <div className="row d-flex align-items-top">
            <div className="enrollment-info-icon">
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
