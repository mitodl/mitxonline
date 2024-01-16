// @flow
import { assert } from "chai"

import NotificationContainer, {
  NotificationContainer as InnerNotificationContainer
} from "./NotificationContainer"
import { TextNotification } from "./notifications"
import { ALERT_TYPE_TEXT } from "../constants"
import IntegrationTestHelper from "../util/integration_test_helper"
import * as notificationsApi from "../lib/notificationsApi"
import sinon from "sinon"

describe("NotificationContainer component", () => {
  const messages = {
    message1: {
      type:  ALERT_TYPE_TEXT,
      props: { text: "derp" }
    }
  }

  let helper, render, getAlertPropsStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    getAlertPropsStub = helper.sandbox
      .stub(notificationsApi, "getNotificationAlertProps")
      .returns({})
    render = helper.configureMountRenderer(
      NotificationContainer,
      InnerNotificationContainer,
      {
        ui: {
          userNotifications: {}
        }
      },
      {}
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("shows notifications", async () => {
    const { inner } = await render({
      ui: {
        userNotifications: messages
      }
    })
    const alerts = inner.find("Alert")
    assert.lengthOf(alerts, Object.keys(messages).length)
    assert.equal(alerts.at(0).prop("children").type, TextNotification)
  })

  it("uses TextNotification as the default inner component", async () => {
    const { inner } = await render({
      ui: {
        userNotifications: {
          aMessage: {
            type:  "unrecognized-type",
            props: { text: "derp" }
          }
        }
      }
    })
    const alerts = inner.find("Alert")
    assert.lengthOf(alerts, Object.keys(messages).length)
    assert.equal(alerts.at(0).prop("children").type, TextNotification)
  })

  ;[
    [undefined, "info"],
    ["danger", "danger"]
  ].forEach(([color, expectedColor]) => {
    it(`shows a ${expectedColor} color notification given a ${String(
      color
    )} color prop`, async () => {
      const { inner } = await render({
        ui: {
          userNotifications: {
            aMessage: {
              type:  ALERT_TYPE_TEXT,
              color: color,
              props: { text: "derp" }
            }
          }
        }
      })
      assert.equal(inner.find("Alert").prop("color"), expectedColor)
      sinon.assert.calledWith(getAlertPropsStub, ALERT_TYPE_TEXT)
    })
  })

  it("uses a default color value for the alert type if a color was not exactly specified", async () => {
    getAlertPropsStub.returns({ color: "some-color" })
    const { inner } = await render({
      ui: {
        userNotifications: {
          aMessage: {
            type:  "some-type",
            props: { text: "derp" }
          }
        }
      }
    })
    assert.equal(inner.find("Alert").prop("color"), "some-color")
    sinon.assert.calledWith(getAlertPropsStub, "some-type")
  })

  it("hides a message when it's dismissed, then removes it from global state", async () => {
    const delayMs = 5
    const { inner, wrapper } = await render(
      {
        ui: {
          userNotifications: messages
        }
      },
      { messageRemoveDelayMs: delayMs }
    )
    const alert = inner.find("Alert").at(0)
    const timeoutPromise = alert.prop("toggle")()
    assert.deepEqual(inner.state(), {
      hiddenNotifications: new Set(["message1"])
    })

    await timeoutPromise
    wrapper.update()
    // Due to changes in rendering due to enzyme, this now returns as undefined. Once Enzyme is no longer in use,
    // This should be modified to expect the same return value as we see when rendered by React.
    assert.deepEqual(wrapper.prop("userNotifications"), undefined)
    assert.deepEqual(inner.state(), { hiddenNotifications: new Set() })
  })
})
