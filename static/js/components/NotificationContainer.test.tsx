import { fireEvent, render, screen } from "@testing-library/react"
import React from "react"
import { ALERT_TYPE_TEXT } from "../constants"
import * as notificationsHooks from "../hooks/notifications"
import { Notifications } from "../hooks/notifications"
import * as notificationsApi from "../lib/notificationsApi"
import { wait } from "../lib/util"
import NotificationContainer from "./NotificationContainer"

describe("NotificationContainer component", () => {
  let contextValue: Notifications, getAlertPropsStub: jest.SpyInstance<any>

  const renderNotifications = (func = render) => func(<NotificationContainer />)

  beforeEach(() => {
    contextValue = {
      addNotification: jest.fn(),
      notifications:   {
        message1: {
          type:      ALERT_TYPE_TEXT,
          dismissed: false,
          props:     {
            text: "blep"
          }
        }
      },
      dismissNotification: jest.fn()
    }
    jest
      .spyOn(notificationsHooks, "useNotifications")
      .mockImplementation(() => {
        return contextValue
      })

    getAlertPropsStub = jest
      .spyOn(notificationsApi, "getNotificationAlertProps")
      .mockReturnValue({})
  })

  it("shows notifications", async () => {
    renderNotifications()

    const alerts = await screen.findAllByRole("alert")

    expect(alerts).toHaveLength(Object.keys(contextValue.notifications).length)
    expect(alerts[0].children[1].innerHTML).toEqual("blep")
  })

  it("uses TextNotification as the default inner component", async () => {
    contextValue.notifications = {
      aMessage: {
        type:      "unrecognized-type",
        dismissed: false,
        props:     {
          text: "blep"
        }
      }
    }
    renderNotifications()

    const alerts = await screen.findAllByRole("alert")

    expect(alerts).toHaveLength(Object.keys(contextValue.notifications).length)
    expect(alerts[0].children[1].innerHTML).toEqual("blep")
  })
  ;[
    [undefined, "info"],
    ["danger", "danger"]
  ].forEach(([color, expectedColor]) => {
    it(`shows a ${expectedColor} color notification given a ${String(
      color
    )} color prop`, async () => {
      contextValue.notifications = {
        aMessage: {
          type:      ALERT_TYPE_TEXT,
          color:     color!,
          dismissed: false,
          props:     {
            text: "blep"
          }
        }
      }

      renderNotifications()

      const alert = await screen.findByRole("alert")

      expect(alert).toHaveClass(`alert-${expectedColor}`)
      expect(getAlertPropsStub).toBeCalledWith(ALERT_TYPE_TEXT)
    })
  })

  it("uses a default color value for the alert type if a color was not exactly specified", async () => {
    getAlertPropsStub.mockReturnValue({
      color: "some-color"
    })
    contextValue.notifications = {
      aMessage: {
        type:  "some-type",
        props: {
          text: "blep"
        }
      }
    }
    renderNotifications()

    const alert = await screen.findByRole("alert")

    expect(alert).toHaveClass("alert-some-color")
    expect(getAlertPropsStub).toBeCalledWith("some-type")
  })

  it("hides a message when it's dismissed, then removes it from global state", async () => {
    const { rerender } = renderNotifications()

    const closeBtn = await screen.findByRole("button")

    await fireEvent.click(closeBtn)

    // simulate useNotifications() internals
    contextValue = {
      ...contextValue,
      notifications: {
        message1: {
          ...contextValue.notifications.message1,
          dismissed: true
        }
      }
    }

    rerender(<NotificationContainer />)

    expect(contextValue.dismissNotification).toBeCalledWith(
      "message1",
      expect.anything()
    )

    await wait(1500)

    const alert = await screen.queryAllByRole("alert")

    expect(alert).toEqual([])
  })
})
