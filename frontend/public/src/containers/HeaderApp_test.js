// @flow
import { assert } from "chai"
import sinon from "sinon"

import HeaderApp, { HeaderApp as InnerHeaderApp } from "./HeaderApp"
import IntegrationTestHelper from "../util/integration_test_helper"
import * as notificationsApi from "../lib/notificationsApi"

describe("Top-level HeaderApp", () => {
  let helper, renderPage, getStoredUserMessageStub, removeStoredUserMessageStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    getStoredUserMessageStub = helper.sandbox
      .stub(notificationsApi, "getStoredUserMessage")
      .returns(null)
    removeStoredUserMessageStub = helper.sandbox.stub(
      notificationsApi,
      "removeStoredUserMessage"
    )
    renderPage = helper.configureMountRenderer(
      HeaderApp,
      InnerHeaderApp,
      {},
      {}
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  /* Because mount will automatically call componentDidMount, I'm simulating a null response from the server
   * to test the loading state.  Until the component gets a positive response, it will continue to not render the header.
   * This includes it receiving no parseable response.  I do have a new test after to show what a positive response does.
   */
  it("fetches user data on load and renders user in the header", async () => {
    helper.handleRequestStub.returns({
      id:               null,
      username:         "",
      email:            null,
      legal_address:    null,
      user_profile:     null,
      is_anonymous:     true,
      is_authenticated: false,
      is_staff:         false,
      is_superuser:     false,
      grants:           [],
      is_active:        false
    })
    const { inner } = await renderPage()
    inner.update()
    // So we look to be sure the next child is there, which is <Header />
    assert.exists(inner.find("Header"))
    sinon.assert.calledWith(helper.handleRequestStub, "/api/users/me", "GET")
  })

  it("tries to fetch user data and no response or an incorrect response renders nothing", async () => {
    helper.handleRequestStub.returns({})
    const { inner } = await renderPage()
    assert.notExists(inner.find("div").prop("children"))
    sinon.assert.calledWith(helper.handleRequestStub, "/api/users/me", "GET")
  })

  it("adds a user notification if a stored message is found in cookies", async () => {
    const userMsg = {
      type: "some-type",
      text: "some text"
    }
    getStoredUserMessageStub.returns(userMsg)
    const { store } = await renderPage()

    const { ui } = store.getState()
    assert.deepEqual(ui.userNotifications, {
      "loaded-user-msg": {
        type:  userMsg.type,
        props: {
          text: userMsg.text
        }
      }
    })
    sinon.assert.calledOnce(removeStoredUserMessageStub)
  })

  it("does not call cart items API for unauthenticated users", async () => {
    helper.handleRequestStub.returns({
      id:               1,
      username:         "testuser",
      email:            "test@example.com",
      legal_address:    null,
      user_profile:     null,
      is_anonymous:     false,
      is_authenticated: false,
      is_staff:         false,
      is_superuser:     false,
      grants:           [],
      is_active:        true
    })
    
    await renderPage()
    
    // Should only call user API, not cart items API
    sinon.assert.calledWith(helper.handleRequestStub, "/api/users/me", "GET")
    sinon.assert.neverCalledWith(helper.handleRequestStub, "/api/checkout/basket_items_count/", "GET")
  })

  it("calls cart items API for authenticated users via componentDidUpdate", async () => {
    // First, simulate component mounting with no user data
    helper.handleRequestStub.returns({})
    const { inner } = await renderPage()
    
    // Now simulate user data being loaded with authenticated user
    const authenticatedUser = {
      id:               1,
      username:         "testuser",
      email:            "test@example.com",
      legal_address:    null,
      user_profile:     null,
      is_anonymous:     false,
      is_authenticated: true,
      is_staff:         false,
      is_superuser:     false,
      grants:           [],
      is_active:        true
    }
    
    // Mock forceRequest to verify it gets called with cart query
    const forceRequestSpy = helper.sandbox.spy()
    inner.setProps({ 
      currentUser : authenticatedUser,
      forceRequest: forceRequestSpy
    })
    inner.update()
    
    // Verify forceRequest was called (this would trigger the cart items query)
    sinon.assert.calledOnce(forceRequestSpy)
  })

  it("passes cart count as 0 for unauthenticated users", async () => {
    helper.handleRequestStub.returns({
      id:               1,
      username:         "testuser",
      email:            "test@example.com",
      legal_address:    null,
      user_profile:     null,
      is_anonymous:     false,
      is_authenticated: false,
      is_staff:         false,
      is_superuser:     false,
      grants:           [],
      is_active:        true
    })
    
    const { inner } = await renderPage()
    inner.setProps({ cartItemsCount: 5 }) // Simulate some cart count in state
    inner.update()
    
    const headerComponent = inner.find("Header")
    assert.equal(headerComponent.prop("cartItemsCount"), 0)
  })

  it("passes actual cart count for authenticated users", async () => {
    helper.handleRequestStub.returns({
      id:               1,
      username:         "testuser",
      email:            "test@example.com",
      legal_address:    null,
      user_profile:     null,
      is_anonymous:     false,
      is_authenticated: true,
      is_staff:         false,
      is_superuser:     false,
      grants:           [],
      is_active:        true
    })
    
    const { inner } = await renderPage()
    inner.setProps({ cartItemsCount: 5 }) // Simulate cart count in state
    inner.update()
    
    const headerComponent = inner.find("Header")
    assert.equal(headerComponent.prop("cartItemsCount"), 5)
  })

})
