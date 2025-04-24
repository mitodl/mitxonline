/* global SETTINGS:false */
import React from "react"
import moment from "moment"
import {
  parseDateString,
  formatPrettyDateTimeAmPmTz,
  formatPrettyMonthDate
} from "../lib/util"
import { Formik, Form, Field } from "formik"
import { Button, Modal, ModalHeader, ModalBody } from "reactstrap"
import { partial, pathOr } from "ramda"
import { createStructuredSelector } from "reselect"
import { compose } from "redux"
import { mutateAsync } from "redux-query"
import { connectRequest } from "redux-query-react"
import { connect } from "react-redux"

import {
  enrollmentsQuery,
  enrollmentsQueryKey,
  deactivateEnrollmentMutation,
  deactivateProgramEnrollmentMutation,
  courseEmailsSubscriptionMutation
} from "../lib/queries/enrollment"
import { currentUserSelector } from "../lib/queries/users"
import { addUserNotification } from "../actions"

import { ALERT_TYPE_DANGER, ALERT_TYPE_SUCCESS } from "../constants"
import GetCertificateButton from "./GetCertificateButton"
import {
  isFinancialAssistanceAvailable,
  isLinkableCourseRun,
  courseRunStatusMessage
} from "../lib/courseApi"
import { isSuccessResponse } from "../lib/util"

import type {
  RunEnrollment,
  Program,
  ProgramEnrollment
} from "../flow/courseTypes"
import type { CurrentUser } from "../flow/authTypes"

type EnrolledItemCardProps = {
  enrollment: RunEnrollment | Program,
  currentUser: CurrentUser,
  deactivateEnrollment: (enrollmentId: number) => Promise<any>,
  deactivateProgramEnrollment: (programId: number) => Promise<any>,
  courseEmailsSubscription: (
    enrollmentId: number,
    emailsSubscription: string
  ) => Promise<any>,
  addUserNotification: Function,
  isLoading: boolean,
  toggleProgramDrawer: Function | null,
  isProgramCard: boolean,
  redirectToCourseHomepage: Function,
  onUnenroll: Function | null,
  onUpdateDrawerEnrollment: Function | null
}

type EnrolledItemCardState = {
  submittingEnrollmentId: number | null,
  emailSettingsModalVisibility: boolean,
  runUnenrollmentModalVisibility: boolean,
  programUnenrollmentModalVisibility: boolean
}

export class EnrolledItemCard extends React.Component<
  EnrolledItemCardProps,
  EnrolledItemCardState
> {
  state = {
    submittingEnrollmentId:             null,
    emailSettingsModalVisibility:       false,
    runUnenrollmentModalVisibility:     false,
    programUnenrollmentModalVisibility: false
  }

  toggleEmailSettingsModalVisibility = () => {
    const { emailSettingsModalVisibility } = this.state
    this.setState({
      emailSettingsModalVisibility: !emailSettingsModalVisibility
    })
  }

  toggleProgramUnenrollmentModalVisibility = () => {
    const { programUnenrollmentModalVisibility } = this.state
    this.setState({
      programUnenrollmentModalVisibility: !programUnenrollmentModalVisibility
    })
  }

  toggleRunUnenrollmentModalVisibility = () => {
    const { runUnenrollmentModalVisibility } = this.state
    this.setState({
      runUnenrollmentModalVisibility: !runUnenrollmentModalVisibility
    })
  }

  toggleProgramInfo = () => {
    const { toggleProgramDrawer, enrollment } = this.props

    if (toggleProgramDrawer !== null) {
      toggleProgramDrawer(enrollment)
    }
  }

  async onDeactivate() {
    this.toggleRunUnenrollmentModalVisibility()
  }

  async onRunUnenrollment(enrollment: RunEnrollment) {
    const { deactivateEnrollment, addUserNotification, onUnenroll } = this.props

    this.toggleRunUnenrollmentModalVisibility()

    this.setState({ submittingEnrollmentId: enrollment.id })
    try {
      const resp = await deactivateEnrollment(enrollment.id)
      let userMessage, messageType
      if (isSuccessResponse(resp)) {
        messageType = ALERT_TYPE_SUCCESS
        userMessage = `You have been successfully unenrolled from ${enrollment.run.title}.`
        if (onUnenroll !== undefined) {
          onUnenroll()
        }
      } else {
        messageType = ALERT_TYPE_DANGER
        userMessage = `Something went wrong with your request to unenroll. Please contact support at ${SETTINGS.support_email}.`
      }
      addUserNotification({
        "unenroll-status": {
          type:  messageType,
          props: {
            text: userMessage
          }
        }
      })
      // Scroll to the top of the page to make sure the user sees the message
      window.scrollTo(0, 0)
    } finally {
      this.setState({ submittingEnrollmentId: null })
    }
  }

  async onProgramUnenrollment(program: Program) {
    const { deactivateProgramEnrollment, addUserNotification, onUnenroll } =
      this.props

    this.toggleProgramUnenrollmentModalVisibility()

    let userMessage, messageType

    try {
      const resp = await deactivateProgramEnrollment(program.id)
      if (isSuccessResponse(resp)) {
        messageType = ALERT_TYPE_SUCCESS
        userMessage = `You have been successfully unenrolled from ${program.title}.`
        if (onUnenroll !== undefined) {
          onUnenroll()
        }
      } else {
        throw new Error("program unenrollment failed")
      }
    } catch (e) {
      messageType = ALERT_TYPE_DANGER
      userMessage = `Something went wrong with your request to unenroll. Please contact support at ${SETTINGS.support_email}.`
    }

    addUserNotification({
      "unenroll-status": {
        type:  messageType,
        props: {
          text: userMessage
        }
      }
    })
    // Scroll to the top of the page to make sure the user sees the message
    window.scrollTo(0, 0)
  }

  async onSubmitEmailSettings(payload: Object) {
    const { courseEmailsSubscription, addUserNotification } = this.props
    this.setState({ submittingEnrollmentId: payload.enrollmentId })
    this.toggleEmailSettingsModalVisibility()
    try {
      const resp = await courseEmailsSubscription(
        payload.enrollmentId,
        payload.subscribeEmails
      )

      let userMessage, messageType
      if (isSuccessResponse(resp)) {
        const message = payload.subscribeEmails ?
          "subscribed to" :
          "unsubscribed from"
        messageType = ALERT_TYPE_SUCCESS
        userMessage = `You have been successfully ${message} course ${payload.courseNumber} emails.`
      } else {
        messageType = ALERT_TYPE_DANGER
        userMessage = `Something went wrong with your request to course ${payload.courseNumber} emails subscription. Please contact support at ${SETTINGS.support_email}.`
      }
      addUserNotification({
        "subscription-status": {
          type:  messageType,
          props: {
            text: userMessage
          }
        }
      })
      // Scroll to the top of the page to make sure the user sees the message
      window.scrollTo(0, 0)
    } finally {
      this.setState({ submittingEnrollmentId: null })
    }
  }

  renderEmailSettingsDialog(enrollment: RunEnrollment) {
    const { emailSettingsModalVisibility } = this.state

    return (
      <Modal
        id={`enrollment-${enrollment.id}-modal`}
        isOpen={emailSettingsModalVisibility}
        toggle={() => this.toggleEmailSettingsModalVisibility()}
      >
        <ModalHeader toggle={() => this.toggleEmailSettingsModalVisibility()}>
          Email Settings
        </ModalHeader>
        <ModalBody>
          <div className="modal-subheader">
            Update your email preferences for{" "}
            <b>{enrollment.run.course_number}</b>
          </div>
          <div className="d-flex callout callout-warning">
            <i className="material-symbols-outlined warning">error</i>
            <p className="p-0">
              Unchecking the box will prevent you from receiving important
              course updates and emails.
            </p>
          </div>
          <Formik
            onSubmit={this.onSubmitEmailSettings.bind(this)}
            initialValues={{
              subscribeEmails: enrollment.edx_emails_subscription,
              enrollmentId:    enrollment.id,
              courseNumber:    enrollment.run.course_number
            }}
          >
            {({ values }) => {
              return (
                <Form>
                  <section>
                    <Field
                      type="hidden"
                      name="enrollmentId"
                      value={values.enrollmentId}
                    />
                    <Field
                      type="hidden"
                      name="courseNumber"
                      value={values.courseNumber}
                    />
                    <Field
                      type="checkbox"
                      name="subscribeEmails"
                      checked={values.subscribeEmails}
                      aria-labelledby={`verified-unenrollment-${values.enrollmentId}-email-checkbox`}
                    />{" "}
                    <label
                      id={`verified-unenrollment-${values.enrollmentId}-email-checkbox`}
                    >
                      Receive course emails
                    </label>
                  </section>
                  <div className="float-container">
                    <Button
                      className="btn btn-gradient-white-to-blue"
                      onClick={() => this.toggleEmailSettingsModalVisibility()}
                    >
                      Cancel
                    </Button>
                    <Button
                      className="btn btn-gradient-red-to-blue"
                      type="submit"
                    >
                      Save Settings
                    </Button>
                  </div>
                </Form>
              )
            }}
          </Formik>
        </ModalBody>
      </Modal>
    )
  }

  renderRunUnenrollmentModal(enrollment: RunEnrollment) {
    const { runUnenrollmentModalVisibility } = this.state
    const now = moment()
    const endDate = enrollment.run.enrollment_end ?
      parseDateString(enrollment.run.enrollment_end) :
      null
    const formattedEndDate = endDate ? formatPrettyDateTimeAmPmTz(endDate) : ""
    return (
      <Modal
        id={`run-unenrollment-${enrollment.id}-modal`}
        isOpen={runUnenrollmentModalVisibility}
        toggle={() => this.toggleRunUnenrollmentModalVisibility()}
        role="dialog"
        aria-labelledby={`run-unenrollment-${enrollment.id}-modal-header`}
        aria-describedby={`run-unenrollment-${enrollment.id}-modal-body`}
      >
        <ModalHeader
          id={`run-unenrollment-${enrollment.id}-modal-header`}
          toggle={() => this.toggleRunUnenrollmentModalVisibility()}
        >
          Unenroll From {enrollment.run.title}
        </ModalHeader>
        <ModalBody id={`run-unenrollment-${enrollment.id}-modal-body`}>
          <p>
            Are you sure you wish to unenroll from {enrollment.run.title}?
            {endDate ?
              now.isAfter(endDate) ?
                " You won't be able to re-enroll." :
                ` You won't be able to re-enroll after ${formattedEndDate}.` :
              null}
          </p>
          {enrollment.enrollment_mode === "verified" ? (
            <p>
              You are enrolled in the certificate track for this course. If you
              wish to request a refund for your payment for this course (if
              any), please{" "}
              <a href="https://mitxonline.zendesk.com/hc/en-us/requests/new">
                contact customer support
              </a>{" "}
              for assistance.
            </p>
          ) : null}
          <div className="float-container">
            <Button
              className="btn btn-gradient-white-to-blue"
              onClick={() => this.toggleRunUnenrollmentModalVisibility()}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              className="btn btn-gradient-red-to-blue"
              onClick={() => this.onRunUnenrollment(enrollment)}
            >
              Unenroll
            </Button>
          </div>
        </ModalBody>
      </Modal>
    )
  }

  renderProgramUnenrollmentModal(enrollment: ProgramEnrollment) {
    const { programUnenrollmentModalVisibility } = this.state

    return (
      <Modal
        id={`program-unenrollment-${enrollment.program.id}-modal`}
        isOpen={programUnenrollmentModalVisibility}
        toggle={() => this.toggleProgramUnenrollmentModalVisibility()}
        role="dialog"
        aria-labelledby={`program-unenrollment-${enrollment.program.id}-modal-header`}
        aria-describedby={`program-unenrollment-${enrollment.program.id}-modal-body`}
      >
        <ModalHeader
          id={`program-unenrollment-${enrollment.program.id}-modal-header`}
          toggle={() => this.toggleProgramUnenrollmentModalVisibility()}
        >
          Unenroll From {enrollment.program.title}
        </ModalHeader>
        <ModalBody
          id={`program-unenrollment-${enrollment.program.id}-modal-body`}
        >
          <p>
            Are you sure you wish to unenroll from {enrollment.program.title}?
            You will not be unenrolled from any courses within the program.
          </p>
          <div className="float-container">
            <Button
              type="submit"
              color="success"
              onClick={() => this.onProgramUnenrollment(enrollment.program)}
            >
              Unenroll
            </Button>{" "}
            <Button
              onClick={() => this.toggleProgramUnenrollmentModalVisibility()}
            >
              Cancel
            </Button>
          </div>
        </ModalBody>
      </Modal>
    )
  }

  renderCourseEnrollment() {
    const { enrollment, currentUser, isProgramCard, redirectToCourseHomepage } =
      this.props
    const financialAssistanceLink =
      isFinancialAssistanceAvailable(enrollment.run) &&
      !enrollment.approved_flexible_price_exists ? (
          <a
            className="finaid-link"
            href={enrollment.run.course.page.financial_assistance_form_url}
          >
          Financial assistance?
          </a>
        ) : null

    const certificateLinksStyles = isProgramCard ?
      "upgrade-item-description d-md-flex align-items-start justify-content-between flex-column" :
      "upgrade-item-description d-md-flex"
    const certificateLinksIntStyles = isProgramCard ?
      "d-flex d-md-flex flex-column align-items-start justify-content-center" :
      "d-flex d-md-flex flex-column justify-content-center"

    const certificateLinks =
      enrollment.run.products.length > 0 &&
      enrollment.enrollment_mode === "audit" &&
      enrollment.run.is_upgradable ? (
          <div className={certificateLinksStyles}>
            <div className={certificateLinksIntStyles}>
              <div className="get-cert-button-container w-100">
                <GetCertificateButton productId={enrollment.run.products[0].id} />
              </div>
            </div>
            <div className="certificate-upgrade-message">
              <strong>Upgrade today</strong> and, upon passing, receive your
            certificate signed by MIT faculty to highlight the knowledge and
            skills you've gained from this MITx course.{" "}
              {enrollment.run.upgrade_deadline ? (
                <b>
                Upgrade expires:{" "}
                  {formatPrettyDateTimeAmPmTz(
                    parseDateString(enrollment.run.upgrade_deadline)
                  )}
                </b>
              ) : null}
            </div>
          </div>
        ) : null

    const onUnenrollClick = partial(this.onDeactivate.bind(this), [enrollment])
    const courseId = enrollment.run.course_number
    const pageLocation =
      enrollment.run.course.page && enrollment.run.course.page.live ?
        enrollment.run.course.page :
        null
    const menuTitle = `Course options for ${enrollment.run.course.title}`

    const courseRunStatusMessageText = courseRunStatusMessage(enrollment.run)

    return (
      <div className="enrolled-item container card" key={enrollment.run.id}>
        <div className="row flex-grow-1 enrolled-item-info">
          {enrollment.run.course.feature_image_src && (
            <div className="col-12 col-md-auto p-0">
              <div className="img-container">
                <img src={enrollment.run.course.feature_image_src} alt="" />
              </div>
            </div>
          )}
          {!enrollment.run.course.feature_image_src &&
            enrollment.run.course.page &&
            enrollment.run.course.page.feature_image_src && (
            <div className="col-12 col-md-auto p-0">
              <div className="img-container">
                <img
                  src={enrollment.run.course.page.feature_image_src}
                  alt=""
                />
              </div>
            </div>
          )}

          <div className="col-12 col-md course-card-text-details d-grid">
            <div className="d-flex justify-content-between flex-nowrap w-100">
              <div className="d-flex flex-column flex-grow-1">
                <div className="align-content-start d-flex enrollment-mode-container flex-wrap pb-1">
                  {enrollment.certificate ? (
                    <span className="badge badge-enrolled-passed mr-2">
                      <img src="/static/images/done.svg" alt="Check" /> Course
                      passed
                    </span>
                  ) : null}
                  {enrollment.enrollment_mode === "verified" ||
                  enrollment.certificate ? (
                      <span className="badge badge-enrolled-verified mr-2">
                      Enrolled in certificate track
                      </span>
                    ) : null}
                </div>

                <h2>{enrollment.run.course.title}</h2>
              </div>
              <div className="d-flex flex-column goto-course-wrapper px-4">
                {isLinkableCourseRun(enrollment.run, currentUser) ? (
                  <a
                    href={enrollment.run.courseware_url}
                    onClick={ev =>
                      redirectToCourseHomepage(
                        enrollment.run.courseware_url,
                        ev
                      )
                    }
                    className="btn btn-primary btn-gradient-red-to-blue"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Go to Course
                  </a>
                ) : (
                  <a
                    className="btn btn-primary btn-gradient-red-to-blue disabled"
                    rel="noopener noreferrer"
                  >
                    Starts{" "}
                    {formatPrettyMonthDate(
                      parseDateString(enrollment.run.start_date)
                    )}
                  </a>
                )}
              </div>
              <button
                className="dropdown-toggle menu-button"
                data-bs-toggle="dropdown"
                aria-haspopup="true"
                aria-expanded="false"
                type="button"
                id={`enrollmentDropdown-${enrollment.id}`}
              >
                <span className="material-icons" title={menuTitle}>
                  more_vert
                </span>
              </button>
              <ul className="dropdown-menu dropdown-menu-end">
                <li className="dropdown-item">
                  <button
                    className="unenroll-btn unstyled d-block"
                    onClick={onUnenrollClick}
                  >
                    Unenroll
                  </button>
                </li>
                <li className="dropdown-item">
                  <button
                    className="unstyled d-block"
                    onClick={() => this.toggleEmailSettingsModalVisibility()}
                  >
                    Email Settings
                  </button>
                </li>
              </ul>
              {this.renderRunUnenrollmentModal(enrollment)}
              {this.renderEmailSettingsDialog(enrollment)}
            </div>
            <div className="detail">
              {courseId}
              {courseRunStatusMessageText}
              <div className="enrollment-extra-links d-flex">
                {pageLocation ? (
                  <a className="pe-2" href={pageLocation.page_url}>
                    Course details
                  </a>
                ) : null}
                {enrollment.certificate ? (
                  <a
                    className="view-certificate"
                    href={enrollment.certificate.link}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    View certificate
                  </a>
                ) : null}
              </div>
            </div>
          </div>
        </div>
        {certificateLinks ? (
          <div className="certificate-row row flex-grow-1">
            <div
              className={`col certificate-container ${
                financialAssistanceLink ? "finaid-link-margin" : ""
              }`}
            >
              {certificateLinks}
            </div>
          </div>
        ) : null}
      </div>
    )
  }

  componentDidUpdate(prevProps: EnrolledItemCardProps) {
    const { onUpdateDrawerEnrollment } = this.props

    if (this.props.enrollment !== prevProps.enrollment) {
      if (onUpdateDrawerEnrollment !== undefined) {
        onUpdateDrawerEnrollment(this.props.enrollment)
      }
    }
  }

  renderProgramEnrollment() {
    const { enrollment } = this.props

    const title = enrollment.program.title
    const certificateLinks = null
    const pageLocation = null
    const courseRunStatusMessageText = null
    const menuTitle = `Program options for ${enrollment.program.title}`
    const courseCount = enrollment.program.courses.length
    const hasPassed = enrollment.certificate ? true : false

    return (
      <div
        className="enrolled-item container card"
        key={`enrolled-program-card-id-${enrollment.program.id}`}
      >
        <div className="row flex-grow-1 enrolled-item-info">
          <div className="col-12 col-md-auto p-0">
            <div className="img-container">
              <img src={enrollment.program.page.feature_image_src} alt="" />
            </div>
          </div>

          <div className="col-12 col-md">
            <div className="d-flex justify-content-between align-content-start flex-nowrap w-100 enrollment-mode-container">
              <div className="d-flex flex-column">
                <div className="align-content-start d-flex enrollment-mode-container flex-wrap pb-1">
                  {hasPassed ? (
                    <span className="badge badge-enrolled-passed mr-2">
                      <img src="/static/images/done.svg" alt="Check" /> Program
                      completed
                    </span>
                  ) : null}
                </div>
                <h2 className="my-0 mr-3">
                  <a
                    rel="noopener noreferrer"
                    href="#program_enrollment_drawer"
                    onClick={() => this.toggleProgramInfo()}
                  >
                    {title}
                  </a>
                </h2>
              </div>
              <button
                className="dropdown-toggle menu-button"
                data-bs-toggle="dropdown"
                aria-haspopup="true"
                aria-expanded="false"
                type="button"
                id={`enrollmentDropdown-${enrollment.id}`}
              >
                <span className="material-icons" title={menuTitle}>
                  more_vert
                </span>
              </button>
              <ul className="dropdown-menu dropdown-menu-end">
                <li className="dropdown-item">
                  <button
                    className="unenroll-btn unstyled d-block"
                    onClick={() =>
                      this.toggleProgramUnenrollmentModalVisibility()
                    }
                  >
                    Unenroll
                  </button>
                </li>
              </ul>
              {this.renderProgramUnenrollmentModal(enrollment)}
            </div>
            <div className="detail detail-program">
              {courseRunStatusMessageText}
              <div className="enrollment-extra-links d-flex pe-2">
                <a
                  className="program-course-count pe-2"
                  rel="noopener noreferrer"
                  href="#program_enrollment_drawer"
                  aria-label="Program's courses"
                  onClick={() => this.toggleProgramInfo()}
                >
                  {courseCount} course
                  {courseCount > 1 ? "s" : null}
                </a>
                {pageLocation ? (
                  <a className="pe-2" href={pageLocation.page_url}>
                    Course details
                  </a>
                ) : null}
                {enrollment.certificate ? (
                  <a
                    className="view-certificate"
                    href={enrollment.certificate.link}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    View program certificate
                  </a>
                ) : null}
              </div>
              <br />
            </div>
          </div>
        </div>
        <div className="row flex-grow-1">
          <div className="col certificate-container">{certificateLinks}</div>
        </div>
      </div>
    )
  }

  render() {
    const { enrollment } = this.props

    return enrollment.run ?
      this.renderCourseEnrollment() :
      this.renderProgramEnrollment()
  }
}

const mapStateToProps = createStructuredSelector({
  currentUser: currentUserSelector,
  isLoading:   pathOr(true, ["queries", enrollmentsQueryKey, "isPending"])
})

const mapPropsToConfig = () => [enrollmentsQuery()]

const deactivateEnrollment = (enrollmentId: number) =>
  mutateAsync(deactivateEnrollmentMutation(enrollmentId))

const deactivateProgramEnrollment = (programId: number) =>
  mutateAsync(deactivateProgramEnrollmentMutation(programId))

const courseEmailsSubscription = (
  enrollmentId: number,
  emailsSubscription: string
) =>
  mutateAsync(
    courseEmailsSubscriptionMutation(enrollmentId, emailsSubscription)
  )

const mapDispatchToProps = {
  deactivateEnrollment,
  deactivateProgramEnrollment,
  courseEmailsSubscription,
  addUserNotification
}

export default compose(
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(EnrolledItemCard)
