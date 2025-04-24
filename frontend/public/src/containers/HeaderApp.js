// @flow
import React from "react"
import { compose } from "redux"
import { connect } from "react-redux"
import { connectRequest } from "redux-query-react"
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
import {
  cartItemsCountQuery,
  cartItemsCountSelector
} from "../lib/queries/cart"

type Props = {
  currentUser: ?CurrentUser,
  cartItemsCount: number,
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
    const { currentUser, cartItemsCount } = this.props

    if (!currentUser) {
      // application is still loading
      return <div />
    }

    return (
      <Header
        currentUser={currentUser}
        cartItemsCount={cartItemsCount}
        location={null}
      />
    )
  }
}

const mapStateToProps = createStructuredSelector({
  currentUser:    currentUserSelector,
  cartItemsCount: cartItemsCountSelector
})

const mapPropsToConfig = () => [cartItemsCountQuery(), users.currentUserQuery()]

const mapDispatchToProps = {
  addUserNotification
}

export default compose(
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(HeaderApp)
