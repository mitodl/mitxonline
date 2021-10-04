/* global SETTINGS: false */
// @flow
import { assert } from "chai"
import sinon from "sinon"

import * as notificationsApi from "./notificationsApi"
import * as api from "./api"
import {
  USER_MSG_COOKIE_NAME,
  USER_MSG_TYPE_COMPLETED_AUTH,
  USER_MSG_TYPE_ENROLL_FAILED,
  USER_MSG_TYPE_ENROLLED
} from "../constants"
import IntegrationTestHelper from "../util/integration_test_helper"

describe("notifications API", () => {
  let helper, getCookieStub, removeCookieStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    getCookieStub = helper.sandbox.stub(api, "getCookie")
    removeCookieStub = helper.sandbox.stub(api, "removeCookie")
  })

  afterEach(() => {
    helper.cleanup()
  })

  describe("parseStoredUserMessage", () => {
    it("returns null if given JSON without the expected properties", () => {
      [{}, { type: null }, { type: "unrecognized" }].forEach(userMsgJson => {
        assert.isNull(notificationsApi.parseStoredUserMessage(userMsgJson))
      })
    })

    it("returns the correct message properties given an 'enrolled' message cookie value", () => {
      assert.deepEqual(
        notificationsApi.parseStoredUserMessage({
          type: USER_MSG_TYPE_ENROLLED,
          run:  "My Run"
        }),
        {
          text: "Success! You've been enrolled in My Run.",
          type: "success"
        }
      )
    })

    it("returns the correct message properties given an 'enroll failed' message cookie value", () => {
      assert.deepEqual(
        notificationsApi.parseStoredUserMessage({
          type: USER_MSG_TYPE_ENROLL_FAILED
        }),
        {
          text: `Something went wrong with your enrollment. Please contact support at ${
            SETTINGS.support_email
          }.`,
          type: "danger"
        }
      )
    })

    it("returns the correct message properties given an 'completed auth' message cookie value", () => {
      assert.deepEqual(
        notificationsApi.parseStoredUserMessage({
          type: USER_MSG_TYPE_COMPLETED_AUTH
        }),
        {
          text: "Account created!",
          type: "success"
        }
      )
    })
  })

  describe("getStoredUserMessage", () => {
    it("returns null if the cookie is not found", () => {
      getCookieStub.returns(null)
      const msg = notificationsApi.getStoredUserMessage()
      assert.isNull(msg)
      sinon.assert.calledWith(getCookieStub, USER_MSG_COOKIE_NAME)
    })

    it("returns a parsed message from the cookie value", () => {
      // Decoded value: {type: "enrolled", run: "Course 2 Run 1"}
      const encodedJsonCookieValue =
        "%7B%22type%22%3A %22enrolled%22%2C %22run%22%3A %22Course 2 Run 1%22%7D"
      getCookieStub.returns(encodedJsonCookieValue)
      const msg = notificationsApi.getStoredUserMessage()
      assert.deepEqual(msg, {
        text: "Success! You've been enrolled in Course 2 Run 1.",
        type: "success"
      })
      sinon.assert.calledWith(getCookieStub, USER_MSG_COOKIE_NAME)
    })
  })

  it("removeStoredUserMessage removes the user message cookie", () => {
    notificationsApi.removeStoredUserMessage()
    sinon.assert.calledWith(removeCookieStub, USER_MSG_COOKIE_NAME)
  })
})
