// @flow
import React from "react"
import { compose } from "redux"
import { connect } from "react-redux"
import { connectRequest } from "redux-query"
import { createStructuredSelector } from "reselect"

import Header from "../components/Header"
import { addUserNotification } from "../actions"
import users, { currentUserSelector } from "../lib/queries/users"
import {
  getStoredUserMessage,
  removeStoredUserMessage
} from "../lib/notificationsApi"

import type { Store } from "redux"
import type { CurrentUser } from "../flow/authTypes"

type Props = {
  currentUser: ?CurrentUser,
  store: Store<*, *>,
  addUserNotification: Function
}

export class HeaderApp extends React.Component<Props, void> {
  componentDidMount() {
    const { addUserNotification } = this.props

    const userMsg = getStoredUserMessage()
    if (userMsg) {
      addUserNotification({
        "loaded-user-msg": {
          type:  userMsg.type,
          props: {
            text: userMsg.text
          }
        }
      })
      removeStoredUserMessage()
    }
  }

  render() {
    const { currentUser } = this.props

    if (!currentUser) {
      // application is still loading
      return <div />
    }

    return <Header currentUser={currentUser} location={null} />
  }
}

const mapStateToProps = createStructuredSelector({
  currentUser: currentUserSelector
})

const mapPropsToConfig = () => [users.currentUserQuery()]

const mapDispatchToProps = {
  addUserNotification
}

export default compose(
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(HeaderApp)
