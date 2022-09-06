import React from "react"

import EnrolledItemCard from "./EnrolledItemCard"
import { routes } from "../lib/urls"

interface ProgramEnrollmentDrawerProps {
  enrollments:  Array<any>,
  showDrawer:   Function,
  isHidden:     boolean,
  currentUser: CurrentUser,
  deactivateEnrollment: (enrollmentId: number) => Promise<any>,
  courseEmailsSubscription: (
    enrollmentId: number,
    emailsSubscription: string
  ) => Promise<any>,
  addUserNotification: Function
}

export class ProgramEnrollmentDrawer extends React.Component<ProgramEnrollmentDrawerProps> {
  render() {
    const {
      isHidden,
      enrollments,
      showDrawer,
      currentUser,
      deactivateEnrollment,
      addUserNotification,
      courseEmailsSubscription,
    } = this.props

    const closeDrawer = () => {
      if (isHidden) {
        showDrawer()
      }
    }

    const backgroundClass = isHidden ? 'drawer-background open' : 'drawer-background'
    const drawerClass = `nav-drawer ${isHidden ? "open" : "closed"}`

    return (
      <>
        <div className={backgroundClass}>
          <div className={drawerClass} id="program_enrollment_drawer" tabIndex="-1" role="dialog" aria-modal="true" aria-label="program courses" aria-describedby="program_enrolled_items">
            <div className="row chrome">
              <button type="button" className="close" aria-label="Close" onClick={closeDrawer}>
                <span aria-hidden="true">
                  &times;
                </span>
              </button>
            </div>
            <div className="row chrome" id="program_enrollment_title">
              <h3>Program courses</h3>
            </div>
            <div className="row enrolled-items" id="program_enrolled_items">
              {enrollments && enrollments.length > 0 ? (enrollments.map(enrollment => (
                <EnrolledItemCard
                  key={enrollment.id}
                  enrollment={enrollment}
                  currentUser={currentUser}
                  deactivateEnrollment={deactivateEnrollment}
                  courseEmailsSubscription={courseEmailsSubscription}
                  addUserNotification={addUserNotification}>
                </EnrolledItemCard>
              ))) : (
                <div className="card no-enrollments p-3 p-md-5 rounded-0 flex-grow-1">
                  <h2>Enroll Now</h2>
                  <p>
                    You are not enrolled in any courses yet. Please{" "}
                    <a href={routes.root}>browse our courses</a>.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </>
    )
  }
}
