// @flow
/* global SETTINGS:false */
import React, { useState } from "react"
import { ReactPageClick } from "react-page-click"
import { Badge } from "reactstrap"

import { generateStartDateText } from "../lib/courseApi"

import type { ProgramEnrollment, Program, RunEnrollment, CourseDetailWithRuns, BaseCourseRun } from "../flow/courseTypes"
import type { CurrentUser } from "../flow/authTypes"

type ProgramEnrollmentCardProps = {
  enrollment: ProgramEnrollment,
  currentUser: CurrentUser,
  deactivateEnrollment: (enrollmentId: number) => Promise<any>,
  courseEmailsSubscription: (
    enrollmentId: number,
    emailsSubscription: string
  ) => Promise<any>,
  addUserNotification: Function,
  showDrawer: Function,
}

type ProgramEnrollmentCardState = {
  submittingEnrollmentId: number | null,
  emailSettingsModalVisibility: boolean,
  verifiedUnenrollmentModalVisibility: boolean,
  menuVisibility: boolean,
  drawerVisibility: boolean,
}

export class ProgramEnrollmentCard extends React.Component<
  ProgramEnrollmentCardProps,
  ProgramEnrollmentCardState
> {
  state = {
    submittingEnrollmentId:              null,
    emailSettingsModalVisibility:        false,
    verifiedUnenrollmentModalVisibility: false,
    menuVisibility:                      false,
    drawerVisibility:                    false,
  }

  hndCloseDrawer = () => {
    this.setState({ drawerVisibility: false })
  }

  hndOpenDrawer = () => {
    const { showDrawer, enrollment } = this.props
    showDrawer(enrollment.enrollments)
  }

  renderDrawer = (drawerClass: string): React$Element<*> | null => {
    const { drawerVisibility } = this.state

    const closeDrawer = () => {
      if (drawerVisibility) {
        this.hndCloseDrawer()
      }
    }

    const backgroundClass = drawerVisibility ? 'drawer-background open' : 'drawer-background'

    return (
      <>
        <div className={backgroundClass}></div>
        <div className={drawerClass}>
          <div className="row">
            <button type="button" className="close" aria-label="Close" onClick={closeDrawer}>
              <span aria-hidden="true">
                x
              </span>
            </button>
          </div>
        </div>
      </>
    )
  }

  render() {
    const {
      enrollment,
    } = this.props

    const {
      drawerVisibility
    } = this.state

    const drawerClass = `nav-drawer ${drawerVisibility ? "open" : "closed"}`

    const title = (
      <a
        href="#"
        rel="noopener noreferrer"
        onClick={() => this.hndOpenDrawer()}
      >
        {enrollment.program.title}
      </a>
    )

    let startDateDescription = null
    let featuredImage = null

    if (enrollment.program.courses.length > 0 && enrollment.program.courses[0].courseruns.length > 0) {
      startDateDescription = generateStartDateText(enrollment.program.courses[0])

      if (enrollment.program.courses[0].feature_image_src) {
        featuredImage = (
          <div className="col-12 col-md-auto px-0 px-md-3">
            <div className="img-container">
              <img
                src={enrollment.program.courses[0].feature_image_src}
                alt="Preview image"
              />
            </div>
          </div>
        )
      }
    }

    // certLocation is not used yet, just here to test layout
    const certLocation = false

    return (
      <div
        className="enrolled-item container card p-md-3 mb-4 rounded-0"
        key={enrollment.program.id}
      >
        <div className="row flex-grow-1">
          {featuredImage}
          <div className="col-12 col-md px-3 py-3 py-md-0">
            <div className="d-flex justify-content-between align-content-start flex-nowrap w-100 enrollment-mode-container">
              <span>
                {enrollment.enrollments.length === 0 ? (<Badge color="red">Not enrolled in any courses</Badge>) : null}
                <Badge className="badge-program">Program</Badge>
              </span>
              <div className="dropdown">
                <button type="button" className="d-inline-flex unstyled dot-menu" onClick={() => this.hndOpenDrawer()}>
                  <i className="material-icons">more_vert</i>
                </button>
              </div>
            </div>
            <div className="d-flex justify-content-between align-content-start flex-nowrap mb-3">
              <h2 className="my-0 mr-3">{title}</h2>
            </div>
            <div className="detail">
              {enrollment.program.readable_id.split('+')[1] || enrollment.program.readable_id}
              {startDateDescription !== null && startDateDescription.active ? (
                <span>|{" "}Starts - {startDateDescription.datestr}</span>
              ) : (
                <span>
                  {startDateDescription === null ? null : (
                    <span>
                      <strong>Active</strong> from{" "}
                      {startDateDescription.datestr}
                    </span>
                  )}
                </span>
              )}
              <div className="enrollment-extra-links d-flex">
                <a href="#" onClick={() => this.hndOpenDrawer()}>{enrollment.enrollments.length} course
                  {enrollment.enrollments.length === 1 ? null : 's'}</a>
                {certLocation ? (
                  <a href={certLocation}>View certificate</a>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }
}

export default ProgramEnrollmentCard
